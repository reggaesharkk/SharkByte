#!/usr/bin/env python3
"""Independently verify a SharkByte Frontier30 full-inverse certificate.

No imports from SharkByte and no numerical simulation. This checks the exact
source bytes, supported ideal gate identities, every indexed cancellation,
and the *unkeyed* JSON record digest. It does not attest a physical run or author.

Run from the repository root:
    python -B tools/verify_roundtrip17_certificate.py \
        examples/high_support/roundtrip_17q.sbq \
        evidence/roundtrip17-inverses.json
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sys

_SOURCE_LIMIT = 65536
_GATE_LIMIT = 256
_IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_NONNEG_INT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")
_SELF_INVERSE = {"h": 1, "x": 1, "z": 1, "cx": 2}
_ANGLE_GATES = {"rx": 1, "ry": 1, "rz": 1, "cp": 2}


class VerificationError(ValueError):
    """An assertion in the certificate or its source failed verification."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record_sha256(body: dict) -> str:
    # Frontier30 uses json.dumps(..., sort_keys=True) with default separators.
    return _sha256(json.dumps(body, sort_keys=True).encode("utf-8"))


def _read_json(path: Path) -> dict:
    def no_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"duplicate certificate key: {key}")
            result[key] = value
        return result

    try:
        record = json.loads(path.read_text(encoding="utf-8"),
                            object_pairs_hook=no_duplicate_keys,
                            parse_constant=lambda value: (_ for _ in ()).throw(
                                VerificationError(f"nonfinite JSON value: {value}")))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise VerificationError(f"cannot read certificate JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise VerificationError("certificate must be a JSON object")
    return record


def _require_exact_int(value: object, label: str, expected: int) -> None:
    if type(value) is not int or value != expected:
        raise VerificationError(f"{label}: expected {expected}, got {value!r}")


def _parse_source(raw: bytes) -> tuple[int, list[tuple]]:
    if len(raw) > _SOURCE_LIMIT:
        raise VerificationError("source exceeds 65536 bytes")
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise VerificationError("source is not UTF-8") from exc
    match = re.fullmatch(r"\s*quantum\s+([A-Za-z_][A-Za-z_0-9]*)\s*\{([^{}]*)\}\s*", source, re.S)
    if not match or not _IDENT.fullmatch(match[1]):
        raise VerificationError("expected a single named Frontier30 quantum block")

    qubits = None
    gates: list[tuple] = []
    measured = False
    for line_no, line in enumerate(match[2].splitlines(), 1):
        line = line.split("//", 1)[0]
        for stmt in line.split(";"):
            tokens = stmt.split()
            if not tokens:
                continue
            op, *args = tokens
            if op == "qubits" and qubits is None and not gates and not measured:
                if len(args) != 1 or not _NONNEG_INT.fullmatch(args[0]):
                    raise VerificationError(f"line {line_no}: invalid qubit count")
                qubits = int(args[0])
                if not 1 <= qubits <= 50:
                    raise VerificationError(f"line {line_no}: qubits must be 1..50")
            elif op in ("shots", "seed") and not measured and qubits is not None and not gates:
                if len(args) != 1 or not _NONNEG_INT.fullmatch(args[0]):
                    raise VerificationError(f"line {line_no}: invalid {op}")
                val = int(args[0])
                if op == "shots" and not 1 <= val <= 100000:
                    raise VerificationError(f"line {line_no}: shots outside range")
                if op == "seed" and not 0 <= val < 2**64:
                    raise VerificationError(f"line {line_no}: seed outside range")
            elif op == "measure_all" and qubits is not None and not measured and not args:
                measured = True
            elif op in _SELF_INVERSE or op in _ANGLE_GATES:
                if qubits is None or measured:
                    raise VerificationError(f"line {line_no}: gate outside circuit")
                arity = _SELF_INVERSE.get(op, _ANGLE_GATES.get(op))
                if len(args) != arity + (op in _ANGLE_GATES):
                    raise VerificationError(f"line {line_no}: invalid {op} operands")
                angle = None
                if op in _ANGLE_GATES:
                    if not _DECIMAL.fullmatch(args[0]):
                        raise VerificationError(f"line {line_no}: invalid angle")
                    try:
                        angle = Decimal(args[0])
                    except InvalidOperation as exc:
                        raise VerificationError(f"line {line_no}: invalid decimal") from exc
                    args = args[1:]
                if any(not _NONNEG_INT.fullmatch(a) for a in args):
                    raise VerificationError(f"line {line_no}: invalid qubit index")
                indices = tuple(int(a) for a in args)
                if len(indices) != arity or any(i >= qubits for i in indices) or len(set(indices)) != len(indices):
                    raise VerificationError(f"line {line_no}: invalid ordered qubit operands")
                gates.append((op, indices, angle))
                if len(gates) > _GATE_LIMIT:
                    raise VerificationError("source gate limit exceeded")
            else:
                raise VerificationError(f"line {line_no}: unsupported or misplaced statement {op!r}")
    if qubits is None or not measured:
        raise VerificationError("missing qubits or final measure_all")
    return qubits, gates


def _inverses(left: tuple, right: tuple) -> bool:
    lop, lindices, la = left
    rop, rindices, ra = right
    if lop != rop or lindices != rindices:
        return False
    if lop in _SELF_INVERSE:
        return True
    if lop in _ANGLE_GATES:
        # Decimal arithmetic checks exact source-decimal opposites without
        # tolerance-based or float-rounding equivalence.
        return la is not None and ra is not None and la + ra == 0
    return False


def _pairs_from_source(gates: list[tuple]) -> tuple[list[list[int]], int]:
    stack: list[tuple[int, tuple]] = []
    pairs: list[list[int]] = []
    for index, gate in enumerate(gates):
        if stack and _inverses(stack[-1][1], gate):
            left, _ = stack.pop()
            pairs.append([left, index])
        else:
            stack.append((index, gate))
    return pairs, len(stack)


def verify(source_file: Path, certificate_file: Path) -> dict:
    try:
        raw = source_file.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read source: {exc}") from exc
    record = _read_json(certificate_file)
    recorded_digest = record.get("record_sha256")
    if not isinstance(recorded_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_digest):
        raise VerificationError("missing/invalid record_sha256")
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    if _record_sha256(body) != recorded_digest:
        raise VerificationError("certificate record SHA-256 mismatch")

    source_digest = _sha256(raw)
    if source_digest != record.get("source_sha256"):
        raise VerificationError("source SHA-256 mismatch")
    if record.get("source") != source_file.name:
        raise VerificationError("certificate source filename mismatch")

    qubits, gates = _parse_source(raw)
    _require_exact_int(record.get("qubits"), "qubits", qubits)
    _require_exact_int(record.get("gates"), "gates", len(gates))
    pairs, remaining = _pairs_from_source(gates)
    recorded_pairs = record.get("cancellation_pairs_zero_based")
    if type(recorded_pairs) is not list or recorded_pairs != pairs or any(
        type(pair) is not list or len(pair) != 2 or any(type(i) is not int for i in pair)
        for pair in recorded_pairs
    ):
        raise VerificationError("indexed cancellation pairs differ from independent reduction")
    _require_exact_int(record.get("executed_gates"), "executed_gates", remaining)
    if remaining:
        raise VerificationError(f"certificate is not a full identity: {remaining} gates remain")
    if len(pairs) * 2 != len(gates):
        raise VerificationError("cancellation does not cover all source gates")
    if record.get("result") != "PASS":
        raise VerificationError("certificate result is not PASS")
    _require_exact_int(record.get("final_populated_states"), "final_populated_states", 1)
    expected_probabilities = {"0" * qubits: 1.0}
    if record.get("probabilities") != expected_probabilities:
        raise VerificationError("recorded probability is inconsistent with identity on |0...0>")
    if record.get("reference_checked") is not False:
        raise VerificationError("certificate must not claim independent reference verification")
    return {
        "status": "CERTIFICATE_VERIFIED",
        "scope": "exact inverse-pair identity in the ideal gate model; not numerical reference or authorship",
        "source_sha256": source_digest,
        "record_sha256": recorded_digest,
        "qubits": qubits,
        "original_gates": len(gates),
        "verified_inverse_pairs": len(pairs),
        "remaining_gates": remaining,
        "expected_final_support": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original .sbq source file")
    parser.add_argument("certificate", type=Path, help="roundtrip17-inverses.json")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.source, args.certificate), indent=2, sort_keys=True))
        return 0
    except VerificationError as exc:
        print(f"CERTIFICATE_REJECTED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())