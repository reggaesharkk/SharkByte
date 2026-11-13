"""Stable v0.6 IR adapter over the authenticated v0.5 parser."""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
VM_REFERENCE = ROOT / "reference" / "vm" / "sharkbyte_v05.py"
SPEC = importlib.util.spec_from_file_location("sharkbyte_v06_vm_reference", VM_REFERENCE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load verified v0.5 parser at {VM_REFERENCE}")
VM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VM
SPEC.loader.exec_module(VM)


class DirectCompileError(Exception):
    pass


@dataclass(frozen=True)
class FunctionIR:
    function_id: int
    name: str
    arity: int
    local_count: int
    body: tuple[Any, ...]


@dataclass(frozen=True)
class ProgramIR:
    source_sha256: str
    functions: tuple[FunctionIR, ...]
    reference_compiler_sha256: str


def _check_expr(node, fn_name):
    kind = node[0]
    if kind in ("num", "var"):
        return
    if kind == "neg":
        _check_expr(node[1], fn_name)
        return
    if kind == "bin":
        if node[1] not in ("+", "-", "*", "/", "%"):
            raise DirectCompileError(f"Unsupported arithmetic operator in {fn_name}: {node[1]}")
        _check_expr(node[2], fn_name)
        _check_expr(node[3], fn_name)
        return
    if kind == "cmp":
        _check_expr(node[2], fn_name)
        _check_expr(node[3], fn_name)
        return
    if kind == "call":
        if len(node[2]) > 8:
            raise DirectCompileError("Direct AArch64 currently supports at most 8 register arguments")
        for arg in node[2]:
            _check_expr(arg, fn_name)
        return
    if kind == "array":
        _check_expr(node[1], fn_name)
        return
    if kind == "index":
        _check_expr(node[2], fn_name)
        return
    raise DirectCompileError(f"Unsupported expression node in {fn_name}: {kind}")


def _check_block(body, fn_name, in_main):
    for stmt in body:
        kind = stmt[0]
        if kind in ("let", "set"):
            _check_expr(stmt[2], fn_name)
        elif kind in ("print", "putc", "return"):
            if kind == "return" and in_main:
                raise DirectCompileError("return is not allowed in main")
            _check_expr(stmt[1], fn_name)
        elif kind == "expr":
            _check_expr(stmt[1], fn_name)
        elif kind == "if":
            _check_expr(stmt[1], fn_name)
            _check_block(stmt[2], fn_name, in_main)
            if stmt[3] is not None:
                _check_block(stmt[3], fn_name, in_main)
        elif kind == "while":
            _check_expr(stmt[1], fn_name)
            _check_block(stmt[2], fn_name, in_main)
        elif kind == "index_set":
            _check_expr(stmt[2], fn_name)
            _check_expr(stmt[3], fn_name)
        else:
            raise DirectCompileError(f"Unsupported statement node in {fn_name}: {kind}")


def lower_source(source: str) -> ProgramIR:
    """Parse to function/slot AST IR; do not emit or execute bytecode here."""
    try:
        functions = VM.V05Parser(source).parse()
    except VM.SharkError as exc:
        raise DirectCompileError(str(exc)) from exc
    if not functions or functions[0]["name"] != "main":
        raise DirectCompileError("Invalid main function")
    ir_functions = []
    for fid, fn in enumerate(functions):
        if fn["arity"] > 8:
            raise DirectCompileError(f"Function {fn['name']} has {fn['arity']} parameters; direct backend limit is 8")
        _check_block(fn["body"], fn["name"], fid == 0)
        ir_functions.append(FunctionIR(fid, fn["name"], fn["arity"], fn["locals"], tuple(fn["body"])))
    return ProgramIR(
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
        tuple(ir_functions),
        hashlib.sha256(VM_REFERENCE.read_bytes()).hexdigest(),
    )
