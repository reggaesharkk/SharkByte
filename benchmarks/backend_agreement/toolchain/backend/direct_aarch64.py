"""Direct AArch64 assembly emitter for the supported SharkByte v0.6 IR."""
from __future__ import annotations

from compiler_ir import DirectCompileError, ProgramIR, lower_source


class AArch64Emitter:
    CONDITIONS = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}

    def __init__(self, ir: ProgramIR):
        self.ir = ir
        self.lines = []
        self.label_id = 0
        self.current_fn = None
        self.local_area = 0
        self.frame_size = 0
        self.saved_offset = 0

    def emit(self, text):
        self.lines.append(text)

    def label(self, stem="L"):
        value = f".L{stem}_{self.label_id}"
        self.label_id += 1
        return value

    def tick(self):
        self.emit("    bl sb_tick")

    def push_pair(self):
        self.emit("    sub sp, sp, #16")
        self.emit("    stp x0, x1, [sp]")

    def check_integer_x1(self, other_tag=None):
        self.emit("    cbnz x1, sb_error_integer")
        if other_tag is not None:
            self.emit(f"    cbnz {other_tag}, sb_error_integer")

    def load_local(self, slot):
        offset = slot * 16
        self.emit(f"    ldp x0, x1, [x29, #{offset}]")

    def expression(self, node):
        self.tick()
        kind = node[0]
        if kind == "num":
            self.emit(f"    ldr x0, ={node[1]}")
            self.emit("    mov x1, #0")
        elif kind == "var":
            self.load_local(node[1])
        elif kind == "neg":
            self.expression(node[1])
            self.check_integer_x1()
            self.emit("    neg x0, x0")
        elif kind == "bin":
            op = node[1]
            self.expression(node[2])
            self.push_pair()
            self.expression(node[3])
            self.emit("    ldr x9, [sp]")
            self.emit("    ldr x10, [sp, #8]")
            self.emit("    add sp, sp, #16")
            self.check_integer_x1("x10")
            if op == "+": self.emit("    add x0, x9, x0")
            elif op == "-": self.emit("    sub x0, x9, x0")
            elif op == "*": self.emit("    mul x0, x9, x0")
            elif op in ("/", "%"):
                safe = self.label("div_safe")
                self.emit("    cbz x0, sb_error_divzero")
                self.emit("    ldr x11, =0x8000000000000000")
                self.emit("    cmp x9, x11")
                self.emit(f"    b.ne {safe}")
                self.emit("    cmn x0, #1")
                self.emit("    b.eq sb_error_divoverflow")
                self.emit(f"{safe}:")
                if op == "/": self.emit("    sdiv x0, x9, x0")
                else:
                    self.emit("    sdiv x2, x9, x0")
                    self.emit("    msub x0, x2, x0, x9")
            else: raise DirectCompileError(f"Unsupported operator: {op}")
            self.emit("    mov x1, #0")
        elif kind == "cmp":
            self.expression(node[2])
            self.push_pair()
            self.expression(node[3])
            self.emit("    ldr x9, [sp]")
            self.emit("    ldr x10, [sp, #8]")
            self.emit("    add sp, sp, #16")
            self.check_integer_x1("x10")
            self.emit("    cmp x9, x0")
            self.emit(f"    cset x0, {self.CONDITIONS[node[1]]}")
            self.emit("    mov x1, #0")
        elif kind == "call":
            target, args = node[1], node[2]
            for arg in args:
                self.expression(arg)
                self.push_pair()
            self.emit("    mov x8, #0")
            for idx in range(len(args)):
                offset = (len(args) - idx - 1) * 16
                tag_done = self.label("arg_int")
                self.emit(f"    ldp x{idx}, x9, [sp, #{offset}]")
                self.emit(f"    cbz x9, {tag_done}")
                self.emit(f"    orr x8, x8, #{1 << idx}")
                self.emit(f"{tag_done}:")
            if args:
                self.emit(f"    add sp, sp, #{len(args) * 16}")
            self.emit(f"    bl sb_fn_{target}")
        elif kind == "array":
            self.expression(node[1])
            self.check_integer_x1()
            self.emit("    bl sb_new_array")
        elif kind == "index":
            self.load_local(node[1])
            self.push_pair()
            self.expression(node[2])
            self.emit("    mov x2, x0")
            self.emit("    mov x3, x1")
            self.emit("    ldp x0, x1, [sp]")
            self.emit("    add sp, sp, #16")
            self.emit("    bl sb_load_index")
        else:
            raise DirectCompileError(f"Unsupported expression: {kind}")

    def enter_function(self, fn):
        self.current_fn = fn
        self.local_area = (fn.local_count * 16 + 15) & ~15
        self.saved_offset = self.local_area
        self.frame_size = self.local_area + 16
        self.emit(f".global sb_fn_{fn.function_id}")
        self.emit(f".type sb_fn_{fn.function_id}, %function")
        self.emit(f"sb_fn_{fn.function_id}:")
        self.emit(f"    mov x9, #{self.frame_size}")
        self.emit("    sub sp, sp, x9")
        self.emit(f"    str x29, [sp, #{self.saved_offset}]")
        self.emit(f"    str x30, [sp, #{self.saved_offset + 8}]")
        self.emit("    mov x29, sp")
        for idx in range(fn.arity):
            self.emit(f"    str x{idx}, [x29, #{idx * 16}]")
            self.emit(f"    ubfx x9, x8, #{idx}, #1")
            self.emit(f"    str x9, [x29, #{idx * 16 + 8}]")
        self.emit("    bl sb_enter")

    def leave_function(self, preserve_result=False):
        if preserve_result:
            self.emit("    sub sp, sp, #16")
            self.emit("    stp x0, x1, [sp]")
        self.emit("    bl sb_leave")
        if preserve_result:
            self.emit("    ldp x0, x1, [sp]")
            self.emit("    add sp, sp, #16")
        self.emit("    mov x9, x29")
        self.emit(f"    ldr x10, [x9, #{self.saved_offset}]")
        self.emit(f"    ldr x30, [x9, #{self.saved_offset + 8}]")
        self.emit("    mov sp, x9")
        self.emit("    mov x29, x10")
        self.emit(f"    mov x11, #{self.frame_size}")
        self.emit("    add sp, sp, x11")
        self.emit("    ret")

    def statement(self, stmt):
        self.tick()
        kind = stmt[0]
        if kind in ("let", "set"):
            self.expression(stmt[2])
            offset = stmt[1] * 16
            self.emit(f"    stp x0, x1, [x29, #{offset}]")
        elif kind == "print":
            self.expression(stmt[1])
            self.check_integer_x1()
            self.emit("    bl sb_print_i64")
        elif kind == "putc":
            self.expression(stmt[1])
            self.check_integer_x1()
            self.emit("    bl sb_putc")
        elif kind == "return":
            self.expression(stmt[1])
            self.leave_function(preserve_result=True)
        elif kind == "expr":
            self.expression(stmt[1])
        elif kind == "index_set":
            self.load_local(stmt[1])
            self.push_pair()
            self.expression(stmt[2])
            self.push_pair()
            self.expression(stmt[3])
            self.emit("    mov x4, x0")
            self.emit("    mov x5, x1")
            self.emit("    ldp x2, x3, [sp]")
            self.emit("    ldp x0, x1, [sp, #16]")
            self.emit("    add sp, sp, #32")
            self.emit("    bl sb_store_index")
        elif kind == "if":
            self.expression(stmt[1])
            self.check_integer_x1()
            otherwise = self.label("else")
            done = self.label("endif")
            self.emit("    cbz x0, " + otherwise)
            for child in stmt[2]: self.statement(child)
            if stmt[3] is not None: self.emit("    b " + done)
            self.emit(otherwise + ":")
            if stmt[3] is not None:
                for child in stmt[3]: self.statement(child)
                self.emit(done + ":")
        elif kind == "while":
            top = self.label("while_top")
            done = self.label("while_end")
            self.emit(top + ":")
            self.expression(stmt[1])
            self.check_integer_x1()
            self.emit("    cbz x0, " + done)
            for child in stmt[2]: self.statement(child)
            self.emit("    b " + top)
            self.emit(done + ":")
        else:
            raise DirectCompileError(f"Unsupported statement: {kind}")

    def generate(self):
        self.emit(".text")
        self.emit(".global _start")
        self.emit(".type _start, %function")
        self.emit("_start:")
        self.emit("    bl sb_fn_0")
        self.emit("    mov x0, #0")
        self.emit("    mov x8, #93")
        self.emit("    svc #0")
        for fn in self.ir.functions:
            self.enter_function(fn)
            for stmt in fn.body:
                self.statement(stmt)
            if fn.function_id == 0:
                self.leave_function()
            else:
                self.emit("    b sb_error_missing_return")
            self.emit(f".size sb_fn_{fn.function_id}, .-sb_fn_{fn.function_id}")
        self.emit('.section .note.GNU-stack,"",%progbits')
        return "\n".join(self.lines) + "\n"


def compile_source(source: str):
    ir = lower_source(source)
    return ir, AArch64Emitter(ir).generate()
