"""Run a SharkByte quantum block with the experimental sparse simulator."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

if __package__:
    from .quantum_frontend import parse
    from .sparse_backend import Circuit, EvolutionStats, ResourceLimitError, evolve, format_basis, probabilities
else:
    from quantum_frontend import parse
    from sparse_backend import Circuit, EvolutionStats, ResourceLimitError, evolve, format_basis, probabilities

DEFAULT_CAP = 4096


def load_circuit(path):
    with path.open("rb") as source:
        data = source.read(65537)
    if len(data) > 65536:
        raise ValueError("Source exceeds 65536 bytes")
    circuit, _ = parse_program(data.decode("utf-8-sig"))
    return circuit, hashlib.sha256(data).hexdigest()


def parse_program(source):
    match = re.fullmatch(r"\s*quantum\s+([A-Za-z_]\w*)\s*\{([^{}]*)\}\s*", source)
    if match is None:
        raise ValueError("Expected one named quantum block")
    parsed = parse(match[2], max_qubits=50, sparse=True)
    gates = []
    for op, args in parsed["gates"]:
        if op == "cp":
            angle, control, target = args
            gates.append((op, control, target, angle))
        elif op in ("rx", "ry", "rz"):
            angle, target = args
            gates.append((op, target, angle))
        else:
            gates.append((op, *args))
    return Circuit(parsed["n"], tuple(gates), match[1]), parsed


def simplify_inverses(circuit):
    """Reduce adjacent inverses in a validated Frontier30 gate stream."""
    stack = []
    pairs = []
    for index, gate in enumerate(circuit.gates):
        if stack:
            left, previous = stack[-1]
            op = gate[0]
            if op in ("h", "x", "z", "cx"):
                inverse = previous == gate
            elif op in ("cp", "rx", "ry", "rz"):
                inverse = previous[:-1] == gate[:-1] and previous[-1] == -gate[-1]
            else:
                inverse = False
            if inverse:
                stack.pop()
                pairs.append((left, index))
                continue
        stack.append((index, gate))
    return Circuit(circuit.qubits, tuple(g for _, g in stack), circuit.name), pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--support-cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--timeout", type=float, default=5.0, help="Evolution deadline in seconds")
    parser.add_argument("--simplify-inverses", action="store_true", help="Cancel adjacent algebraic inverses before evolution")
    args = parser.parse_args()
    try:
        circuit, source_digest = load_circuit(args.source)
        stats = EvolutionStats()
        report = dict(source=args.source.name, source_sha256=source_digest,
                      qubits=circuit.qubits, gates=len(circuit.gates),
                      support_cap=args.support_cap, timeout_seconds=args.timeout)
        if args.simplify_inverses:
            circuit, pairs = simplify_inverses(circuit)
            report.update(cancellation_pairs_zero_based=pairs, executed_gates=len(circuit.gates))
        start = time.perf_counter()
        try:
            state = evolve(circuit, support_cap=args.support_cap, max_seconds=args.timeout, stats=stats)
        except ResourceLimitError as exc:
            report.update(result="REFUSED", reason=str(exc), refused_gate_index=exc.gate_index,
                          requested_support=exc.requested_support)
        else:
            report.update(result="PASS", reference_checked=False, final_populated_states=len(state))
        report.update(evolution_seconds=time.perf_counter() - start,
                      peak_populated_states=stats.peak_support, peak_gate_index=stats.peak_gate_index)
        if report["result"] == "PASS":
            probs = probabilities(state, circuit.qubits)
            report["probabilities"] = {
                format_basis(basis, circuit.qubits): probs[basis] for basis in sorted(probs)
            }
    except (OSError, ValueError, ArithmeticError) as exc:
        parser.error(str(exc))
    report["record_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
