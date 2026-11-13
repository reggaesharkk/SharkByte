import argparse
import dataclasses
import os
import pathlib
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile

MAGIC = b"SBVM"
HEADER = struct.Struct("<4sBHI")
MASK = (1 << 64) - 1
BYTECODE_VERSION = 1
BYTECODE_V2_VERSION = 2
COMPILER_VERSION = "0.5-dev-hardening"
V2_MAGIC = b"FN05"
V2_PREFIX = struct.Struct("<4sH")
V2_FUNCTION = struct.Struct("<HHHI")
MAX_LOCALS = 1024
MAX_CALL_DEPTH = 128
MAX_OPERAND_STACK = 65536
MAX_ARRAY_LENGTH = 65536
MAX_HEAP_ELEMENTS = 65536
MAX_ARRAYS = 4096

OPS = {
    "PUSH": 1, "LOAD": 2, "STORE": 3,
    "ADD": 16, "SUB": 17, "MUL": 18,
    "NEG": 19,
    "CMP_EQ": 33, "CMP_NE": 34, "CMP_LT": 35, "CMP_LE": 36, "CMP_GT": 37, "CMP_GE": 38,
    "BRZ": 40, "BRNZ": 41, "JMP": 42,
    "DIV": 43, "MOD": 44,
    "PRINT": 32, "PUTC": 45,
    "CALL": 46, "RET": 47, "NEW_ARRAY": 48,
    "LOAD_INDEX": 49, "STORE_INDEX": 50, "MISSING_RET": 51, "POP": 52,
    "HALT": 255
}

OPERAND_FMT = {
    "PUSH": "<q",
    "LOAD": "<H",
    "STORE": "<H",
    "BRZ": "<i",
    "BRNZ": "<i",
    "JMP": "<i",
    "CALL": "<HH",
}

CMP_OPS = {
    "==": "CMP_EQ",
    "!=": "CMP_NE",
    "<":  "CMP_LT",
    "<=": "CMP_LE",
    ">":  "CMP_GT",
    ">=": "CMP_GE",
}

KEYWORDS = frozenset(("let", "print", "putc", "if", "else", "while", "fun", "return", "array"))

ARM64_COND = {
    "CMP_EQ": "eq",
    "CMP_NE": "ne",
    "CMP_LT": "lt",
    "CMP_LE": "le",
    "CMP_GT": "gt",
    "CMP_GE": "ge",
}

class SharkError(Exception):
    pass

def signed(x):
    x &= MASK
    return x if x < (1 << 63) else x - (1 << 64)

def trunc_divmod(a, b):
    """Exact signed i64 quotient/remainder, truncating quotient toward zero."""
    if b == 0:
        raise SharkError("Division by zero")
    if a == -(1 << 63) and b == -1:
        raise SharkError("Integer division overflow")
    quotient = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        quotient = -quotient
    remainder = a - quotient * b
    return quotient, remainder

PATTERN = re.compile(
    r"\s+|//[^\n]*|\d+|[A-Za-z_]\w*|==|!=|<=|>=|[=;<>{}(),\[\]+\-*/%<>!]"
)

def tokenize(src):
    out = []
    pos = 0
    while pos < len(src):
        m = PATTERN.match(src, pos)
        if not m:
            raise SharkError(f"Invalid character at {pos}")
        s = m.group()
        if not s.isspace() and not s.startswith("//"):
            out.append(s)
        pos = m.end()
    return out + ["<EOF>"]

class Parser:
    def __init__(self, src):
        self.tokens = tokenize(src)
        self.i = 0
        self.known = set()

    def peek(self):
        return self.tokens[self.i]

    def eat(self, expected=None):
        x = self.peek()
        if expected is not None and x != expected:
            raise SharkError(f"Expected {expected}, got {x}")
        self.i += 1
        return x

    def identifier(self):
        x = self.peek()
        if not re.fullmatch(r"[A-Za-z_]\w*", x):
            raise SharkError(f"Invalid identifier: {x}")
        if x in KEYWORDS:
            raise SharkError(f"Reserved word: {x}")
        return self.eat()

    def factor(self):
        if self.peek() == "-":
            self.eat("-")
            return ("neg", self.factor())

        if self.peek() == "(":
            self.eat("(")
            x = self.expr()
            self.eat(")")
            return x

        x = self.peek()
        if x.isdigit():
            self.eat()
            n = int(x)
            if n > (1 << 63) - 1:
                raise SharkError("Integer literal exceeds i64")
            return ("num", n)

        name = self.identifier()
        if name not in self.known:
            raise SharkError(f"Undefined variable: {name}")
        return ("var", name)

    def term(self):
        x = self.factor()
        while self.peek() in ("*", "/", "%"):
            op = self.eat()
            x = ("bin", op, x, self.factor())
        return x

    def expr(self):
        x = self.term()
        while self.peek() in ("+", "-"):
            op = self.eat()
            x = ("bin", op, x, self.term())
        return x

    def comparison(self):
        x = self.expr()
        if self.peek() in CMP_OPS:
            op = self.eat()
            y = self.expr()
            return ("cmp", op, x, y)
        return x

    def block(self):
        self.eat("{")
        stmts = []
        while self.peek() != "}":
            if self.peek() == "<EOF>":
                raise SharkError("Unterminated block")
            stmts.append(self.statement())
        self.eat("}")
        return stmts

    def statement(self):
        if self.peek() == "let":
            self.eat("let")
            name = self.identifier()
            if name in self.known:
                raise SharkError("Duplicate variable: " + name)
            self.eat("=")
            value = self.comparison()
            self.eat(";")
            self.known.add(name)
            return ("let", name, value)
        elif self.peek() == "print":
            self.eat("print")
            value = self.comparison()
            self.eat(";")
            return ("print", value)
        elif self.peek() == "putc":
            self.eat("putc")
            value = self.comparison()
            self.eat(";")
            return ("putc", value)
        elif self.peek() == "if":
            self.eat("if")
            self.eat("(")
            cond = self.comparison()
            self.eat(")")
            then_block = self.block()
            else_block = None
            if self.peek() == "else":
                self.eat("else")
                else_block = self.block()
            return ("if", cond, then_block, else_block)
        elif self.peek() == "while":
            self.eat("while")
            self.eat("(")
            cond = self.comparison()
            self.eat(")")
            body_block = self.block()
            return ("while", cond, body_block)
        else:
            name = self.identifier()
            if name not in self.known:
                raise SharkError("Undefined variable: " + name)
            self.eat("=")
            value = self.comparison()
            self.eat(";")
            return ("set", name, value)

    def program(self):
        out = []
        while self.peek() != "<EOF>":
            out.append(self.statement())
        return out

def compile_v04_source(source):
    statements = Parser(source).program()
    slots = {}

    class CodeBuffer:
        def __init__(self):
            self.instructions = []
            self.fixups = []
            self.labels = {}

        def _byte_offset(self, upto_index):
            total = 0
            for i in range(upto_index):
                name, _ = self.instructions[i]
                total += 1
                if name == "PUSH":
                    total += 8
                elif name in ("LOAD", "STORE"):
                    total += 2
                elif name in ("BRZ", "BRNZ", "JMP"):
                    total += 4
            return total

        def emit(self, opname, arg=None):
            self.instructions.append((opname, arg))
            return len(self.instructions) - 1

        def label(self, name):
            self.labels[name] = self._byte_offset(len(self.instructions))

        def fixup(self, index, label_name):
            self.fixups.append((index, label_name))

        def resolve(self):
            for index, label_name in self.fixups:
                if label_name not in self.labels:
                    raise SharkError(f"Undefined label: {label_name}")
                target = self.labels[label_name]
                current = self._byte_offset(index) + 5  # opcode(1) + int32 operand(4)
                offset = target - current
                if offset < -(1 << 31) or offset >= (1 << 31):
                    raise SharkError(f"Jump offset out of int32 range: {offset}")
                self.instructions[index] = (self.instructions[index][0], offset)

    code = CodeBuffer()
    if_counter = [0]
    while_counter = [0]

    def expression(node):
        kind = node[0]
        if kind == "num":
            code.emit("PUSH", node[1])
        elif kind == "var":
            code.emit("LOAD", slots[node[1]])
        elif kind == "neg":
            expression(node[1])
            code.emit("NEG", None)
        elif kind == "bin":
            expression(node[2])
            expression(node[3])
            op = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}[node[1]]
            code.emit(op, None)
        elif kind == "cmp":
            expression(node[2])
            expression(node[3])
            code.emit(CMP_OPS[node[1]], None)

    def compile_block(block):
        for stmt in block:
            kind = stmt[0]
            if kind == "let":
                expression(stmt[2])
                slot = len(slots)
                if slot >= 65535:
                    raise SharkError("Too many variables")
                slots[stmt[1]] = slot
                code.emit("STORE", slot)
            elif kind == "set":
                expression(stmt[2])
                code.emit("STORE", slots[stmt[1]])
            elif kind == "print":
                expression(stmt[1])
                code.emit("PRINT", None)
            elif kind == "putc":
                expression(stmt[1])
                code.emit("PUTC", None)
            elif kind == "if":
                _, cond, then_block, else_block = stmt
                expression(cond)
                if else_block is not None:
                    else_label = f"L_if_else_{if_counter[0]}"
                    end_label = f"L_if_end_{if_counter[0]}"
                    if_counter[0] += 1
                    else_idx = code.emit("BRZ", None)
                    compile_block(then_block)
                    end_idx = code.emit("JMP", None)
                    code.label(else_label)
                    compile_block(else_block)
                    code.label(end_label)
                    code.fixup(else_idx, else_label)
                    code.fixup(end_idx, end_label)
                else:
                    end_label = f"L_if_end_{if_counter[0]}"
                    if_counter[0] += 1
                    exit_idx = code.emit("BRZ", None)
                    compile_block(then_block)
                    code.label(end_label)
                    code.fixup(exit_idx, end_label)
            elif kind == "while":
                _, cond, body_block = stmt
                loop_label = f"L_while_loop_{while_counter[0]}"
                exit_label = f"L_while_exit_{while_counter[0]}"
                while_counter[0] += 1
                code.label(loop_label)
                expression(cond)
                exit_idx = code.emit("BRZ", None)
                compile_block(body_block)
                jmp_idx = code.emit("JMP", None)
                code.label(exit_label)
                code.fixup(exit_idx, exit_label)
                code.fixup(jmp_idx, loop_label)

    for statement in statements:
        compile_block([statement])

    code.emit("HALT")
    code.resolve()

    flat_code = [(name, arg) for name, arg in code.instructions]
    return len(slots), flat_code


class V2Program(list):
    """Function code records for the isolated v0.5 bytecode container."""
    def __init__(self, functions):
        super().__init__(functions[0]["code"])
        self.functions = functions


class V05Parser:
    def __init__(self, source):
        self.tokens = tokenize(source)
        self.i = 0
        self.signatures = {}
        self.functions = []

    def peek(self, offset=0):
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def eat(self, expected=None):
        token = self.peek()
        if expected is not None and token != expected:
            raise SharkError(f"Expected {expected}, got {token}")
        self.i += 1
        return token

    def ident(self):
        token = self.peek()
        if not re.fullmatch(r"[A-Za-z_]\w*", token) or token in KEYWORDS:
            raise SharkError(f"Invalid identifier: {token}")
        return self.eat()

    def block(self, scopes, next_slot, params_scope=False):
        self.eat("{")
        if not params_scope:
            scopes.append({})
        stmts = []
        while self.peek() != "}":
            if self.peek() == "<EOF>":
                raise SharkError("Unterminated block")
            stmts.append(self.statement(scopes, next_slot))
        self.eat("}")
        if not params_scope:
            scopes.pop()
        return stmts

    def lookup(self, name, scopes):
        for scope in reversed(scopes):
            if name in scope:
                return scope[name]
        raise SharkError("Undefined variable: " + name)

    def statement(self, scopes, next_slot):
        t = self.peek()
        if t == "let":
            self.eat(); name = self.ident(); scope = scopes[-1]
            if name in scope:
                raise SharkError("Duplicate variable: " + name)
            self.eat("="); value = self.expr(scopes); self.eat(";")
            slot = next_slot[0]; next_slot[0] += 1
            if slot >= MAX_LOCALS: raise SharkError("Too many local variables")
            scope[name] = slot
            return ("let", slot, value)
        if t in ("print", "putc"):
            self.eat(); value = self.expr(scopes); self.eat(";")
            return (t, value)
        if t == "return":
            self.eat(); value = self.expr(scopes); self.eat(";")
            return ("return", value)
        if t == "if":
            self.eat(); self.eat("("); cond = self.comparison(scopes); self.eat(")")
            yes = self.block(scopes, next_slot)
            no = self.block(scopes, next_slot) if self.peek() == "else" and (self.eat() or True) else None
            return ("if", cond, yes, no)
        if t == "while":
            self.eat(); self.eat("("); cond = self.comparison(scopes); self.eat(")")
            return ("while", cond, self.block(scopes, next_slot))
        if t == "fun" or t == "array":
            raise SharkError(f"Unexpected {t} in statement")
        if re.fullmatch(r"[A-Za-z_]\w*", t) and self.peek(1) == "[":
            name = self.eat(); slot = self.lookup(name, scopes); self.eat("[")
            index = self.expr(scopes); self.eat("]")
            if self.peek() == "=":
                self.eat(); value = self.expr(scopes); self.eat(";")
                return ("index_set", slot, index, value)
            self.eat(";"); return ("expr", ("index", slot, index))
        if re.fullmatch(r"[A-Za-z_]\w*", t) and self.peek(1) == "=":
            name = self.eat(); slot = self.lookup(name, scopes); self.eat("=")
            value = self.expr(scopes); self.eat(";"); return ("set", slot, value)
        value = self.expr(scopes); self.eat(";"); return ("expr", value)

    def factor(self, scopes):
        if self.peek() == "-":
            self.eat(); return ("neg", self.factor(scopes))
        if self.peek() == "(":
            self.eat(); node = self.expr(scopes); self.eat(")"); return node
        if self.peek().isdigit():
            n = int(self.eat())
            if n > (1 << 63) - 1: raise SharkError("Integer literal exceeds i64")
            return ("num", n)
        if self.peek() == "array":
            self.eat(); self.eat("("); size = self.expr(scopes); self.eat(")")
            return ("array", size)
        name = self.ident()
        if self.peek() == "(":
            self.eat(); args = []
            if self.peek() != ")":
                args.append(self.expr(scopes))
                while self.peek() == ",": self.eat(); args.append(self.expr(scopes))
            self.eat(")")
            if name not in self.signatures: raise SharkError("Undefined function: " + name)
            fn, arity = self.signatures[name]
            if len(args) != arity: raise SharkError(f"Function {name} expects {arity} arguments, got {len(args)}")
            return ("call", fn, args)
        slot = self.lookup(name, scopes)
        if self.peek() == "[":
            self.eat(); index = self.expr(scopes); self.eat("]"); return ("index", slot, index)
        return ("var", slot)

    def term(self, scopes):
        node = self.factor(scopes)
        while self.peek() in ("*", "/", "%"):
            op = self.eat(); node = ("bin", op, node, self.factor(scopes))
        return node

    def expr(self, scopes):
        node = self.term(scopes)
        while self.peek() in ("+", "-"):
            op = self.eat(); node = ("bin", op, node, self.term(scopes))
        return node

    def comparison(self, scopes):
        node = self.expr(scopes)
        if self.peek() in CMP_OPS:
            op = self.eat(); node = ("cmp", op, node, self.expr(scopes))
        return node

    def parse(self):
        # First pass validates declaration names/arity, allowing forward calls.
        cursor = 0
        while cursor < len(self.tokens) - 1:
            if self.tokens[cursor] != "fun":
                cursor += 1; continue
            name = self.tokens[cursor + 1]
            if not re.fullmatch(r"[A-Za-z_]\w*", name): raise SharkError("Invalid function name")
            if name in self.signatures: raise SharkError("Duplicate function: " + name)
            j = cursor + 2
            if self.tokens[j] != "(": raise SharkError("Expected ( after function name")
            j += 1; arity = 0; expect_name = True
            while self.tokens[j] != ")":
                if expect_name:
                    arg = self.tokens[j]
                    if not re.fullmatch(r"[A-Za-z_]\w*", arg) or arg in KEYWORDS: raise SharkError("Invalid parameter")
                    arity += 1; j += 1; expect_name = False
                elif self.tokens[j] == ",": j += 1; expect_name = True
                else: raise SharkError("Malformed parameter list")
            if expect_name and arity: raise SharkError("Malformed parameter list")
            self.signatures[name] = (len(self.signatures) + 1, arity)
            cursor = j + 1
        declarations = []
        main_stmts = []
        self.i = 0
        # Parse top-level sequence; function declarations are skipped from main.
        while self.peek() != "<EOF>":
            if self.peek() != "fun":
                main_scopes = getattr(self, "main_scopes", None)
                if main_scopes is None: self.main_scopes = [{}]
                # Main variable slots are shared across top-level statements.
                slots = getattr(self, "main_next_slot", [0])
                self.main_next_slot = slots
                main_stmts.append(self.statement(self.main_scopes, slots))
                continue
            self.eat(); name = self.ident(); self.eat("("); params = []
            if self.peek() != ")":
                params.append(self.ident())
                while self.peek() == ",": self.eat(); params.append(self.ident())
            self.eat(")")
            if len(params) != self.signatures[name][1]: raise SharkError("Malformed function declaration")
            scopes = [{}]; next_slot = [0]
            for param in params:
                if param in scopes[0]: raise SharkError("Duplicate parameter: " + param)
                scopes[0][param] = next_slot[0]; next_slot[0] += 1
            body = self.block(scopes, next_slot, params_scope=True)
            declarations.append({"name": name, "arity": len(params), "locals": next_slot[0], "body": body})
        main_locals = getattr(self, "main_next_slot", [0])[0]
        self.functions = [{"name": "main", "arity": 0, "locals": main_locals, "body": main_stmts}]
        ordered = [None] * (len(self.signatures) + 1); ordered[0] = self.functions[0]
        for fn in declarations: ordered[self.signatures[fn["name"]][0]] = fn
        if any(fn is None for fn in ordered): raise SharkError("Invalid function table")
        return ordered


def compile_v05_source(source):
    functions = V05Parser(source).parse()
    compiled = []
    for fid, fn in enumerate(functions):
        ins = []; fixups = []; labels = {}; counter = [0]
        def size(op): return 5 if op in ("BRZ", "BRNZ", "JMP") else 3 if op in ("LOAD", "STORE") else 9 if op == "PUSH" else 5 if op == "CALL" else 1
        def offset(end): return sum(size(op) for op, _ in ins[:end])
        def emit(op, arg=None): ins.append((op, arg)); return len(ins)-1
        def label():
            name = f"L{counter[0]}"; counter[0] += 1; labels[name] = offset(len(ins)); return name
        def jump(op, target): fixups.append((emit(op, None), target))
        def expression(node):
            kind = node[0]
            if kind == "num": emit("PUSH", node[1])
            elif kind == "var": emit("LOAD", node[1])
            elif kind == "neg": expression(node[1]); emit("NEG")
            elif kind == "bin": expression(node[2]); expression(node[3]); emit({"+":"ADD","-":"SUB","*":"MUL","/":"DIV","%":"MOD"}[node[1]])
            elif kind == "cmp": expression(node[2]); expression(node[3]); emit(CMP_OPS[node[1]])
            elif kind == "call":
                for arg in node[2]: expression(arg)
                emit("CALL", (node[1], len(node[2])))
            elif kind == "array": expression(node[1]); emit("NEW_ARRAY")
            elif kind == "index": emit("LOAD", node[1]); expression(node[2]); emit("LOAD_INDEX")
            else: raise SharkError("Unsupported expression")
        def statements(body):
            for stmt in body:
                k = stmt[0]
                if k in ("let", "set"): expression(stmt[2]); emit("STORE", stmt[1])
                elif k in ("print", "putc"): expression(stmt[1]); emit(k.upper())
                elif k == "return":
                    if fid == 0: raise SharkError("return is not allowed in main")
                    expression(stmt[1]); emit("RET")
                elif k == "expr": expression(stmt[1]); emit("POP")
                elif k == "index_set": emit("LOAD", stmt[1]); expression(stmt[2]); expression(stmt[3]); emit("STORE_INDEX")
                elif k == "if":
                    expression(stmt[1]); no = label(); jump("BRZ", no)
                    statements(stmt[2])
                    if stmt[3] is not None:
                        end = label(); jump("JMP", end); labels[no] = offset(len(ins)); statements(stmt[3]); labels[end] = offset(len(ins))
                    else: labels[no] = offset(len(ins))
                elif k == "while":
                    top = label(); expression(stmt[1]); end = label(); jump("BRZ", end); statements(stmt[2]); jump("JMP", top); labels[end] = offset(len(ins))
        statements(fn["body"])
        if fid == 0: emit("HALT")
        else: emit("MISSING_RET")
        for idx, target in fixups:
            if target not in labels: raise SharkError("Invalid branch target")
            op, _ = ins[idx]; ins[idx] = (op, labels[target] - (offset(idx) + size(op)))
        compiled.append({"name": fn["name"], "arity": fn["arity"], "locals": fn["locals"], "code": ins})
    return len(compiled), V2Program(compiled)


def compile_source(source):
    tokens = tokenize(source)
    let_names = [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == "let"]
    needs_scopes = len(let_names) != len(set(let_names))
    if any(t in ("fun", "array", "return") or t == "[" for t in tokens) or needs_scopes:
        return compile_v05_source(source)
    return compile_v04_source(source)


def encode(slots, code):
    if isinstance(code, V2Program):
        if not 1 <= len(code.functions) <= 65535:
            raise SharkError("Invalid function count")
        payload = bytearray(V2_PREFIX.pack(V2_MAGIC, len(code.functions)))
        for fn in code.functions:
            name = fn["name"].encode("utf-8")
            if len(name) > 65535 or fn["locals"] > MAX_LOCALS:
                raise SharkError("Function metadata exceeds limits")
            body = bytearray()
            for opname, arg in fn["code"]:
                if opname not in OPS: raise SharkError("Unknown opcode name")
                body.append(OPS[opname])
                if opname == "PUSH": body.extend(struct.pack("<q", arg))
                elif opname in ("LOAD", "STORE"): body.extend(struct.pack("<H", arg))
                elif opname in ("BRZ", "BRNZ", "JMP"): body.extend(struct.pack("<i", arg))
                elif opname == "CALL": body.extend(struct.pack("<HH", *arg))
            payload.extend(V2_FUNCTION.pack(fn["arity"], fn["locals"], len(name), len(body)))
            payload.extend(name); payload.extend(body)
        return HEADER.pack(MAGIC, BYTECODE_V2_VERSION, len(code.functions), len(payload)) + payload
    payload = bytearray()
    for name, arg in code:
        payload.append(OPS[name])
        fmt = OPERAND_FMT.get(name)
        if fmt is not None:
            if name in ("BRZ", "BRNZ", "JMP"):
                # arg is a signed int32 relative offset
                payload.extend(struct.pack(fmt, arg))
            elif name == "PUSH":
                payload.extend(struct.pack("<q", arg))
            elif name in ("LOAD", "STORE"):
                payload.extend(struct.pack("<H", arg))
    return HEADER.pack(MAGIC, BYTECODE_VERSION, slots, len(payload)) + payload


def decode_v2(binary):
    if len(binary) < HEADER.size: raise SharkError("Truncated header")
    magic, version, count, size = HEADER.unpack_from(binary)
    if magic != MAGIC or version != BYTECODE_V2_VERSION or len(binary) != HEADER.size + size:
        raise SharkError("Invalid SharkByte format")
    pos = HEADER.size
    if pos + V2_PREFIX.size > len(binary): raise SharkError("Truncated v2 header")
    tag, fncount = V2_PREFIX.unpack_from(binary, pos); pos += V2_PREFIX.size
    if tag != V2_MAGIC or fncount != count or not fncount: raise SharkError("Invalid v2 function table")
    fns = []
    for _ in range(fncount):
        if pos + V2_FUNCTION.size > len(binary): raise SharkError("Truncated function descriptor")
        arity, locals_count, name_len, code_len = V2_FUNCTION.unpack_from(binary, pos); pos += V2_FUNCTION.size
        if locals_count > MAX_LOCALS or arity > locals_count: raise SharkError("Invalid function limits")
        end_name = pos + name_len; end_code = end_name + code_len
        if end_code > len(binary): raise SharkError("Truncated function body")
        try: name = binary[pos:end_name].decode("utf-8")
        except UnicodeDecodeError as exc: raise SharkError("Invalid function name encoding") from exc
        fns.append({"name": name, "arity": arity, "locals": locals_count,
                    "start": end_name, "end": end_code, "code": binary[end_name:end_code]})
        pos = end_code
    if pos != len(binary): raise SharkError("Trailing v2 data")
    if fns[0]["name"] != "main" or fns[0]["arity"] != 0: raise SharkError("Invalid main function")
    names_seen = set()
    for fn in fns:
        if not fn["name"] or fn["name"] in names_seen:
            raise SharkError("Invalid or duplicate function name")
        names_seen.add(fn["name"])
    # Decode every function before execution. Operand reads and branches may
    # not escape a function or land in the middle of an instruction operand.
    opcode_names = {value: name for name, value in OPS.items()}
    operand_sizes = {"PUSH": 8, "LOAD": 2, "STORE": 2,
                     "BRZ": 4, "BRNZ": 4, "JMP": 4, "CALL": 4}
    for fid, fn in enumerate(fns):
        pc = fn["start"]
        starts = set()
        branches = []
        calls = []
        while pc < fn["end"]:
            starts.add(pc)
            opcode = binary[pc]
            pc += 1
            name = opcode_names.get(opcode)
            if name is None:
                raise SharkError(f"Unknown opcode: {opcode}")
            size = operand_sizes.get(name, 0)
            if pc + size > fn["end"]:
                raise SharkError("Truncated operand")
            if name in ("BRZ", "BRNZ", "JMP"):
                offset = struct.unpack_from("<i", binary, pc)[0]
                branches.append((pc + 4 + offset))
            elif name == "CALL":
                target, argc = struct.unpack_from("<HH", binary, pc)
                calls.append((target, argc))
            elif name == "HALT" and fid != 0:
                raise SharkError("HALT outside main")
            elif name == "RET" and fid == 0:
                raise SharkError("RET from main")
            elif name == "MISSING_RET" and fid == 0:
                raise SharkError("MISSING_RET in main")
            pc += size
        for target in branches:
            if target not in starts:
                raise SharkError("Branch target is not an instruction boundary")
        for target, argc in calls:
            if target == 0 or target >= len(fns):
                raise SharkError("Invalid function target")
            if argc != fns[target]["arity"]:
                raise SharkError("Function arity mismatch")
    return fns


def run_vm_v2(binary, max_steps=None, stats=None, stop_check=None):
    fns = decode_v2(binary)
    frames = [{"fid": 0, "pc": fns[0]["start"], "base": 0, "locals": [0] * fns[0]["locals"]}]
    stack = []; output = []; steps = 0; heap = {}; next_handle = 1; heap_elements = 0; peak_frames = 1
    def pop():
        if not stack: raise SharkError("Stack underflow")
        return stack.pop()
    def operand(fmt, frame):
        pc = frame["pc"]; s = struct.Struct(fmt)
        if pc + s.size > fns[frame["fid"]]["end"]: raise SharkError("Truncated operand")
        value = s.unpack_from(binary, pc); frame["pc"] += s.size
        return value[0] if len(value) == 1 else value
    def int_value(v):
        if not isinstance(v, int): raise SharkError("Expected integer value")
        return v
    while frames:
        frame = frames[-1]; fn = fns[frame["fid"]]
        if frame["pc"] >= fn["end"]: raise SharkError("Missing HALT")
        if max_steps is not None and steps >= max_steps:
            if stats is not None: stats.update(instructions=steps, instructions_executed=steps, step_limit_checks=steps + 1)
            raise SharkError("Execution step limit exceeded")
        steps += 1
        if stats is not None:
            stats.update(instructions=steps, instructions_executed=steps, frames_max=peak_frames,
                         heap_arrays=len(heap), heap_elements=heap_elements)
        if stop_check is not None and steps % 4096 == 0 and stop_check():
            raise SharkError("Execution cancelled")
        op = binary[frame["pc"]]; frame["pc"] += 1
        if op == OPS["PUSH"]: stack.append(operand("<q", frame))
        elif op in (OPS["LOAD"], OPS["STORE"]):
            idx = operand("<H", frame)
            if idx >= len(frame["locals"]): raise SharkError("Invalid local index")
            if op == OPS["LOAD"]: stack.append(frame["locals"][idx])
            else: frame["locals"][idx] = pop()
        elif op in (OPS["ADD"], OPS["SUB"], OPS["MUL"]):
            b = int_value(pop()); a = int_value(pop())
            stack.append(signed(a+b) if op == OPS["ADD"] else signed(a-b) if op == OPS["SUB"] else signed(a*b))
        elif op in (OPS["DIV"], OPS["MOD"]):
            b = int_value(pop()); a = int_value(pop()); q, r = trunc_divmod(a,b); stack.append(q if op == OPS["DIV"] else r)
        elif op == OPS["NEG"]: stack.append(signed(-int_value(pop())))
        elif op in tuple(OPS[f"CMP_{x}"] for x in ("EQ","NE","LT","LE","GT","GE")):
            b=int_value(pop()); a=int_value(pop())
            stack.append(int((a==b) if op==OPS["CMP_EQ"] else (a!=b) if op==OPS["CMP_NE"] else (a<b) if op==OPS["CMP_LT"] else (a<=b) if op==OPS["CMP_LE"] else (a>b) if op==OPS["CMP_GT"] else (a>=b)))
        elif op in (OPS["BRZ"], OPS["BRNZ"], OPS["JMP"]):
            off=operand("<i",frame)
            if op==OPS["JMP"] or (op==OPS["BRZ"] and int_value(pop())==0) or (op==OPS["BRNZ"] and int_value(pop())!=0): frame["pc"]+=off
            if not fn["start"] <= frame["pc"] < fn["end"]: raise SharkError("Branch outside function")
        elif op == OPS["PRINT"]: output.append(str(int_value(pop()))+"\n")
        elif op == OPS["PUTC"]:
            value=int_value(pop())
            if not 0<=value<=127: raise SharkError("Character code outside ASCII range 0..127")
            output.append(chr(value))
        elif op == OPS["CALL"]:
            target, argc = operand("<HH", frame)
            if target == 0 or target >= len(fns): raise SharkError("Invalid function target")
            callee=fns[target]
            if argc != callee["arity"]: raise SharkError("Function arity mismatch")
            if len(frames) >= MAX_CALL_DEPTH: raise SharkError("Call depth limit exceeded")
            if len(stack)<argc: raise SharkError("Stack underflow")
            args=stack[-argc:] if argc else []
            if argc: del stack[-argc:]
            if len(stack)>MAX_OPERAND_STACK-1: raise SharkError("Operand stack limit exceeded")
            local=[0]*callee["locals"]
            local[:argc]=args
            frames.append({"fid":target,"pc":callee["start"],"base":len(stack),"locals":local})
            peak_frames=max(peak_frames,len(frames))
        elif op == OPS["RET"]:
            if frame["fid"] == 0: raise SharkError("RET from main")
            if len(stack) != frame["base"]+1: raise SharkError("Invalid return stack balance")
            value=pop(); frames.pop(); stack.append(value)
        elif op == OPS["MISSING_RET"]: raise SharkError("Function ended without return")
        elif op == OPS["POP"]: pop()
        elif op == OPS["NEW_ARRAY"]:
            n=int_value(pop())
            if n<0: raise SharkError("Negative array length")
            if n>MAX_ARRAY_LENGTH or len(heap)>=MAX_ARRAYS or heap_elements+n>MAX_HEAP_ELEMENTS: raise SharkError("Array heap limit exceeded")
            handle=next_handle; next_handle+=1; heap[handle]=[0]*n; heap_elements+=n; stack.append(("array",handle))
        elif op in (OPS["LOAD_INDEX"], OPS["STORE_INDEX"]):
            value=int_value(pop()) if op==OPS["STORE_INDEX"] else None
            index=int_value(pop()); ref=pop()
            if not (isinstance(ref,tuple) and len(ref)==2 and ref[0]=="array" and ref[1] in heap): raise SharkError("Expected array reference")
            if index<0 or index>=len(heap[ref[1]]): raise SharkError("Array index out of bounds")
            if op==OPS["LOAD_INDEX"]: stack.append(heap[ref[1]][index])
            else: heap[ref[1]][index]=value
        elif op == OPS["HALT"]:
            if frame["fid"] != 0 or len(frames)!=1 or stack: raise SharkError("Invalid final VM state")
            if frame["pc"] != fn["end"]: raise SharkError("Invalid final VM state")
            if stats is not None: stats.update(instructions=steps,instructions_executed=steps,frames_max=peak_frames,heap_arrays=len(heap),heap_elements=heap_elements)
            return "".join(output)
        else: raise SharkError(f"Unknown opcode: {op}")
        if len(stack)>MAX_OPERAND_STACK: raise SharkError("Operand stack limit exceeded")
    raise SharkError("Missing HALT")


def run_vm(binary, max_steps=None, stats=None, stop_check=None):
    if len(binary) < HEADER.size:
        raise SharkError("Truncated header")
    magic, version, count, size = HEADER.unpack_from(binary)
    if magic == MAGIC and version == BYTECODE_V2_VERSION:
        return run_vm_v2(binary, max_steps=max_steps, stats=stats, stop_check=stop_check)
    if magic != MAGIC or version != BYTECODE_VERSION:
        raise SharkError("Invalid SharkByte format")
    if len(binary) != HEADER.size + size:
        raise SharkError("Invalid binary length")

    pc = HEADER.size
    stack = []
    variables = [0] * count
    output = []
    steps = 0

    def pop():
        if not stack:
            raise SharkError("Stack underflow")
        return stack.pop()

    def read(fmt):
        nonlocal pc
        f = struct.Struct(fmt)
        if pc + f.size > len(binary):
            raise SharkError("Truncated operand")
        value = f.unpack_from(binary, pc)[0]
        pc += f.size
        return value

    while pc < len(binary):
        if max_steps is not None or stats is not None or stop_check is not None:
            steps += 1
        if max_steps is not None:
            if steps > max_steps:
                if stats is not None:
                    stats["instructions"] = steps
                    stats["instructions_executed"] = max_steps
                    stats["step_limit_checks"] = steps
                raise SharkError("Execution step limit exceeded")
        if stats is not None:
            # Count only dispatched VM instructions; the limit-rejected next
            # instruction is recorded separately and is not an execution.
            stats["instructions_executed"] = steps
        if stop_check is not None and steps % 4096 == 0 and stop_check():
            raise SharkError("Execution cancelled")

        op = binary[pc]
        pc += 1

        if op == OPS["PUSH"]:
            stack.append(read("<q"))
        elif op in (OPS["LOAD"], OPS["STORE"]):
            index = read("<H")
            if index >= count:
                raise SharkError("Invalid variable index")
            if op == OPS["LOAD"]:
                stack.append(variables[index])
            else:
                variables[index] = pop()
        elif op in (OPS["ADD"], OPS["SUB"], OPS["MUL"]):
            b, a = pop(), pop()
            if op == OPS["ADD"]:
                stack.append(signed(a + b))
            elif op == OPS["SUB"]:
                stack.append(signed(a - b))
            else:
                stack.append(signed(a * b))
        elif op in (OPS["DIV"], OPS["MOD"]):
            b, a = pop(), pop()
            quotient, remainder = trunc_divmod(a, b)
            stack.append(quotient if op == OPS["DIV"] else remainder)
        elif op == OPS["NEG"]:
            stack.append(signed(-pop()))
        elif op == OPS["CMP_EQ"]:
            b, a = pop(), pop()
            stack.append(1 if a == b else 0)
        elif op == OPS["CMP_NE"]:
            b, a = pop(), pop()
            stack.append(1 if a != b else 0)
        elif op == OPS["CMP_LT"]:
            b, a = pop(), pop()
            stack.append(1 if a < b else 0)
        elif op == OPS["CMP_LE"]:
            b, a = pop(), pop()
            stack.append(1 if a <= b else 0)
        elif op == OPS["CMP_GT"]:
            b, a = pop(), pop()
            stack.append(1 if a > b else 0)
        elif op == OPS["CMP_GE"]:
            b, a = pop(), pop()
            stack.append(1 if a >= b else 0)
        elif op == OPS["BRZ"]:
            offset = read("<i")
            if pop() == 0:
                pc += offset
        elif op == OPS["BRNZ"]:
            offset = read("<i")
            if pop() != 0:
                pc += offset
        elif op == OPS["JMP"]:
            offset = read("<i")
            pc += offset
        elif op == OPS["PRINT"]:
            output.append(str(pop()) + "\n")
        elif op == OPS["PUTC"]:
            value = pop()
            if not 0 <= value <= 127:
                raise SharkError("Character code outside ASCII range 0..127")
            output.append(chr(value))
        elif op == OPS["HALT"]:
            if stack or pc != len(binary):
                raise SharkError("Invalid final VM state")
            if stats is not None:
                stats["instructions"] = steps
            return "".join(output)
        else:
            raise SharkError(f"Unknown opcode: {op}")
    raise SharkError("Missing HALT")


def disassemble(binary):
    """Return verified textual instructions from a complete SharkByte binary."""
    if len(binary) < HEADER.size:
        raise SharkError("Truncated header")
    magic, version, _slots, size = HEADER.unpack_from(binary)
    if magic == MAGIC and version == BYTECODE_V2_VERSION:
        fns = decode_v2(binary)
        names = {value: key for key, value in OPS.items()}
        fmt_map = {"PUSH":"<q", "LOAD":"<H", "STORE":"<H", "BRZ":"<i", "BRNZ":"<i", "JMP":"<i", "CALL":"<HH"}
        output = []
        for fid, fn in enumerate(fns):
            output.append(f"FUNCTION {fid} {fn['name']} arity={fn['arity']} locals={fn['locals']}")
            pc = fn["start"]
            while pc < fn["end"]:
                op = binary[pc]; pc += 1; name = names.get(op)
                if name is None: raise SharkError(f"Unknown opcode: {op}")
                fmt = fmt_map.get(name)
                if fmt:
                    try: values = struct.unpack_from(fmt, binary, pc)
                    except struct.error as exc: raise SharkError("Truncated operand") from exc
                    pc += struct.calcsize(fmt)
                    arg = ",".join(map(str, values))
                    output.append(f"  {name} {arg}")
                else: output.append(f"  {name}")
        return "\n".join(output)
    if magic != MAGIC or version != BYTECODE_VERSION:
        raise SharkError("Invalid SharkByte format")
    if len(binary) != HEADER.size + size:
        raise SharkError("Invalid binary length")
    names = {value: key for key, value in OPS.items()}
    formats = {"PUSH": "<q", "LOAD": "<H", "STORE": "<H",
               "BRZ": "<i", "BRNZ": "<i", "JMP": "<i"}
    pc = HEADER.size
    lines = []
    while pc < len(binary):
        opcode = binary[pc]
        pc += 1
        name = names.get(opcode)
        if name is None:
            raise SharkError(f"Unknown opcode: {opcode}")
        fmt = formats.get(name)
        if fmt:
            try:
                value = struct.unpack_from(fmt, binary, pc)[0]
            except struct.error as exc:
                raise SharkError("Truncated operand") from exc
            pc += struct.calcsize(fmt)
            if name in ("PUSH", "LOAD", "STORE"):
                lines.append(f"{name} {value}")
            else:
                lines.append(f"{name} offset={value}")
        else:
            lines.append(name)
    return "\n".join(lines) if lines else "Empty"


def arm64(slots, code):
    lines = [".text", ".global _start", "_start:"]
    uses_division = any(name in ("DIV", "MOD") for name, _ in code)
    uses_putc = any(name == "PUTC" for name, _ in code)

    def emit(*items):
        lines.extend("    " + item for item in items)

    def push():
        emit("str x0, [sp, #-16]!")

    def pop():
        emit("ldr x0, [sp], #16")

    # First pass: compute byte offset for each instruction index
    byte_offsets = []
    total = 0
    for name, arg in code:
        byte_offsets.append(total)
        total += 1
        if name == "PUSH":
            total += 8
        elif name in ("LOAD", "STORE"):
            total += 2
        elif name in ("BRZ", "BRNZ", "JMP"):
            total += 4

    # Map target byte offsets to labels
    label_map = {}  # target_byte_offset -> label_name
    label_counter = 0
    for i, (name, arg) in enumerate(code):
        if name in ("BRZ", "BRNZ", "JMP"):
            current_byte = byte_offsets[i] + 5
            target_byte = current_byte + arg
            if target_byte not in label_map:
                label_map[target_byte] = f".L{label_counter}"
                label_counter += 1

    # Second pass: emit assembly
    for i, (name, arg) in enumerate(code):
        if byte_offsets[i] in label_map:
            lines.append(label_map[byte_offsets[i]] + ":")

        if name == "PUSH":
            bits = arg & MASK
            emit(f"movz x0, #{bits & 65535}")
            for shift in (16, 32, 48):
                chunk = (bits >> shift) & 65535
                if chunk:
                    emit(f"movk x0, #{chunk}, lsl #{shift}")
            push()
        elif name == "LOAD":
            emit(
                f"adrp x9, sb_var_{arg}",
                f"add x9, x9, :lo12:sb_var_{arg}",
                "ldr x0, [x9]"
            )
            push()
        elif name == "STORE":
            pop()
            emit(
                f"adrp x9, sb_var_{arg}",
                f"add x9, x9, :lo12:sb_var_{arg}",
                "str x0, [x9]"
            )
        elif name in ("ADD", "SUB", "MUL"):
            emit(
                "ldr x1, [sp], #16",
                "ldr x0, [sp], #16"
            )
            instr = {"ADD": "add", "SUB": "sub", "MUL": "mul"}[name]
            emit(f"{instr} x0, x0, x1")
            push()
        elif name in ("DIV", "MOD"):
            emit(
                "ldr x1, [sp], #16",  # divisor b
                "ldr x0, [sp], #16",  # dividend a
                "cbz x1, .L_divzero",
                "movz x2, #32768, lsl #48",  # INT64_MIN
                "cmp x0, x2",
                f"b.ne .L_div_valid_{i}",
                "movn x3, #0",  # -1
                "cmp x1, x3",
                "b.eq .L_divoverflow",
                f".L_div_valid_{i}:",
            )
            if name == "DIV":
                emit("sdiv x0, x0, x1")
            else:
                emit("sdiv x2, x0, x1", "msub x0, x2, x1, x0")
            push()
        elif name == "NEG":
            pop()
            emit("neg x0, x0")
            push()
        elif name in ("CMP_EQ", "CMP_NE", "CMP_LT", "CMP_LE", "CMP_GT", "CMP_GE"):
            emit(
                "ldr x1, [sp], #16",
                "ldr x0, [sp], #16",
                f"cmp x0, x1",
                f"cset x0, {ARM64_COND[name]}",
            )
            push()
        elif name == "BRZ":
            pop()
            current_byte = byte_offsets[i] + 5
            target_byte = current_byte + arg
            emit(f"cbz x0, {label_map[target_byte]}")
        elif name == "BRNZ":
            pop()
            current_byte = byte_offsets[i] + 5
            target_byte = current_byte + arg
            emit(f"cbnz x0, {label_map[target_byte]}")
        elif name == "JMP":
            current_byte = byte_offsets[i] + 5
            target_byte = current_byte + arg
            emit(f"b {label_map[target_byte]}")
        elif name == "PRINT":
            pop()
            emit("bl sb_print_i64")
        elif name == "PUTC":
            pop()
            emit("bl sb_putc_ascii")
        elif name == "HALT":
            emit("mov x0, #0", "mov x8, #93", "svc #0")

    if uses_division:
        lines += [
            "",
            ".L_divzero:",
            "    mov x0, #1",
            "    mov x8, #93",
            "    svc #0",
            ".L_divoverflow:",
            "    mov x0, #2",
            "    mov x8, #93",
            "    svc #0",
        ]

    if uses_putc:
        lines += [
            "",
            "sb_putc_ascii:",
            "    cmp x0, #0",
            "    b.lt .L_putc_range_error",
            "    cmp x0, #127",
            "    b.gt .L_putc_range_error",
            "    mov w10, w0",
            ".L_putc_retry:",
            "    adrp x1, sb_putc_byte",
            "    add x1, x1, :lo12:sb_putc_byte",
            "    strb w10, [x1]",
            "    mov x0, #1",
            "    mov x2, #1",
            "    mov x8, #64",
            "    svc #0",
            "    cmp x0, #1",
            "    b.eq .L_putc_return",
            "    cmn x0, #4",
            "    b.eq .L_putc_retry",
            "    mov x0, #4",
            "    mov x8, #93",
            "    svc #0",
            ".L_putc_range_error:",
            "    mov x0, #3",
            "    mov x8, #93",
            "    svc #0",
            ".L_putc_return:",
            "    ret",
        ]

    lines += [
        "",
        "sb_print_i64:",
        "    sub sp, sp, #64",
        "    add x4, sp, #63",
        "    mov w5, #10",
        "    strb w5, [x4]",
        "    mov x6, x0",
        "    mov w7, #0",
        "    cmp x6, #0",
        "    b.ge .Lpositive",
        "    mov w7, #1",
        "    neg x6, x6",
        ".Lpositive:",
        "    mov x9, #10",
        ".Ldigits:",
        "    udiv x10, x6, x9",
        "    msub x11, x10, x9, x6",
        "    add w11, w11, #48",
        "    sub x4, x4, #1",
        "    strb w11, [x4]",
        "    mov x6, x10",
        "    cbnz x6, .Ldigits",
        "    cbz w7, .Lwrite",
        "    sub x4, x4, #1",
        "    mov w11, #45",
        "    strb w11, [x4]",
        ".Lwrite:",
        "    mov x0, #1",
        "    mov x1, x4",
        "    add x2, sp, #64",
        "    sub x2, x2, x4",
        "    mov x8, #64",
        "    svc #0",
        "    add sp, sp, #64",
        "    ret",
    ]

    if slots or uses_putc:
        lines += ["", ".bss", ".balign 8"]
        for i in range(slots):
            lines += [f"sb_var_{i}:", "    .zero 8"]
        if uses_putc:
            lines += ["sb_putc_byte:", "    .zero 1"]

    return "\n".join(lines) + "\n"


def native(assembly, destination):
    clang = shutil.which("clang")
    if not clang:
        raise SharkError("Clang is required for native compilation")
    build_root = os.environ.get("SHARKBYTE_BUILD_DIR")
    managed_temp = None
    if build_root:
        root = pathlib.Path(build_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            for _ in range(8):
                candidate = root / f"sharkbyte-{secrets.token_hex(8)}"
                try:
                    candidate.mkdir()
                    managed_temp = candidate
                    break
                except FileExistsError:
                    continue
                except OSError as exc:
                    raise SharkError(f"Temporary build directory is not writable: {root}") from exc
            if managed_temp is None:
                raise SharkError(f"Unable to allocate a unique temporary build directory under {root}")
        except OSError as exc:
            raise SharkError(f"Temporary build directory is unavailable: {root}") from exc
        folder = str(managed_temp)
    else:
        managed_temp = pathlib.Path(tempfile.mkdtemp(prefix="sharkbyte-"))
        folder = str(managed_temp)
    try:
        source = pathlib.Path(folder) / "sharkbyte.s"
        source.write_text(assembly)
        command = [
            clang, "--target=aarch64-linux-gnu",
            "-fuse-ld=lld", "-nostdlib", "-static", "-no-pie",
            "-Wl,-e,_start", "-Wl,--build-id=none",
            str(source), "-o", str(destination)
        ]
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=20
            )
        except subprocess.TimeoutExpired as exc:
            raise SharkError("Native compiler exceeded 20-second time limit") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no compiler diagnostics").strip()
            raise SharkError(f"Native compilation failed (exit {completed.returncode}): {detail}")
    finally:
        if managed_temp is not None:
            shutil.rmtree(managed_temp, ignore_errors=True)
    data = pathlib.Path(destination).read_bytes()
    if data[:4] != b"\x7fELF":
        raise SharkError("Not an ELF executable")
    if struct.unpack_from("<H", data, 18)[0] != 183:
        raise SharkError("Not ARM64")
    return destination

def selftest():
    cases = [
        ("print 2 + 3 * 4;", "14\n"),
        ("let x = 40; let y = 2; print x+y;", "42\n"),
        ("let x=10; x=x*3; print -x;", "-30\n"),
        ("print 9223372036854775807 + 1;",
         "-9223372036854775808\n"),
        ("let x = 40; let y = 2; print x + y; x = x * 3; print x;",
         "42\n120\n"),
        ("print 10 - 3 + 2;", "9\n"),
        ("print 7 * 6 - 1;", "41\n"),
        ("print (1 + 2) * (3 + 4);", "21\n"),
        ("print -5;", "-5\n"),
        ("print 3 - 10;", "-7\n"),
        ("print -(-4);", "4\n"),
        ("let n = -3; print n * n;", "9\n"),
        ("let n = -9223372036854775807; print n - 1;",
         "-9223372036854775808\n"),
        ("let m = -9223372036854775807; let n = m - 1; print -n;",
         "-9223372036854775808\n"),
        ("print 9223372036854775807 * 2;", "-2\n"),
        # Comparisons (i64 signed, produce 0/1)
        ("print 5 == 5;", "1\n"),
        ("print 5 == 6;", "0\n"),
        ("print 5 != 6;", "1\n"),
        ("print 5 != 5;", "0\n"),
        ("print 3 < 5;", "1\n"),
        ("print 5 < 3;", "0\n"),
        ("print 5 <= 5;", "1\n"),
        ("print 5 <= 3;", "0\n"),
        ("print 7 > 3;", "1\n"),
        ("print 3 > 7;", "0\n"),
        ("print 7 >= 7;", "1\n"),
        ("print 3 >= 7;", "0\n"),
        # Comparison with arithmetic precedence
        ("print 2 + 3 * 4 == 14;", "1\n"),
        ("print 2 + 3 * 4 == 15;", "0\n"),
        # Negative comparisons
        ("print -5 < -3;", "1\n"),
        ("print -5 > -3;", "0\n"),
        # If/else
        ("let x = 0; if (1) { x = 42; } print x;", "42\n"),
        ("let x = 0; if (0) { x = 42; } print x;", "0\n"),
        ("let x = 0; if (1) { x = 10; } else { x = 20; } print x;", "10\n"),
        ("let x = 0; if (0) { x = 10; } else { x = 20; } print x;", "20\n"),
        # While loops
        ("let x = 0; while (x < 3) { x = x + 1; } print x;", "3\n"),
        ("let x = 5; while (x > 0) { x = x - 1; } print x;", "0\n"),
        ("let x = 0; while (0) { x = 42; } print x;", "0\n"),
        ("let x = 0; while (x < 5) { x = x + 2; } print x;", "6\n"),
        # Comparison edge values
        ("print 9223372036854775807 >= 9223372036854775807;", "1\n"),
        ("let m = -9223372036854775807; print m <= m;", "1\n"),
        ("let m = -9223372036854775807; print m < 0;", "1\n"),
    ]

    for source, expected in cases:
        slots, code = compile_source(source)
        result = run_vm(encode(slots, code))
        if result != expected:
            raise SharkError(f"Self-test failed: {source!r} got {result!r} expected {expected!r}")
    for invalid in ("print missing;", "let x=1; let x=2;", "print ;", "let 1 = 2;", "print u;", "if (1) {", "while (1) {"):
        try:
            compile_source(invalid)
        except SharkError:
            pass
        else:
            raise SharkError(f"Invalid source accepted: {invalid!r}")

    def expect_error(label, binary):
        try:
            run_vm(binary)
        except SharkError:
            return
        raise SharkError(f"Expected VM error: {label}")

    expect_error("truncated header", b"SBVM")
    expect_error("bad magic", HEADER.pack(b"XXXX", 1, 0, 0))
    expect_error("bad version", HEADER.pack(MAGIC, 2, 0, 0))
    expect_error("invalid binary length", HEADER.pack(MAGIC, 1, 0, 5))
    expect_error("print on empty stack", encode(0, [("PRINT", None)]))
    expect_error("add with one operand", encode(0, [("ADD", None), ("HALT", None)]))
    expect_error("halt with leftover stack", encode(0, [("PUSH", 5), ("HALT", None)]))
    expect_error("load out of range", encode(0, [("LOAD", 7), ("HALT", None)]))
    expect_error("store out of range", encode(0, [("STORE", 7), ("HALT", None)]))
    expect_error("unknown opcode", HEADER.pack(MAGIC, 1, 0, 1) + bytes([200]))
    expect_error("missing HALT", encode(0, [("PUSH", 1)]))
    expect_error("truncated operand", HEADER.pack(MAGIC, 1, 0, 1) + bytes([1]))
    print("SharkByte VM self-tests PASSED")
    print("ARM64 native backend requires separate local testing")

def main():
    parser = argparse.ArgumentParser(prog="sharkbyte")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "compile", "asm", "native"):
        p = sub.add_parser(command)
        p.add_argument("source")
        if command != "run":
            p.add_argument("-o", "--output", required=True)
    p = sub.add_parser("vm")
    p.add_argument("bytecode")
    sub.add_parser("test")
    args = parser.parse_args()

    try:
        if args.command == "test":
            selftest()
            return
        if args.command == "vm":
            print(run_vm(pathlib.Path(args.bytecode).read_bytes()),
                  end="")
            return
        source = pathlib.Path(args.source).read_text(encoding="utf-8")
        slots, code = compile_source(source)
        if args.command == "run":
            print(run_vm(encode(slots, code)), end="")
        elif args.command == "compile":
            pathlib.Path(args.output).write_bytes(encode(slots, code))
        elif args.command == "asm":
            pathlib.Path(args.output).write_text(arm64(slots, code))
        elif args.command == "native":
            print("Created:", native(arm64(slots, code), args.output))
    except (SharkError, OSError, subprocess.CalledProcessError) as e:
        print("SharkByte error:", e, file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
