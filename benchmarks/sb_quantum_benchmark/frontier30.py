"""Run a SharkByte quantum block with the experimental sparse simulator."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from quantum_frontend import parse
from sparse_backend import Circuit, EvolutionStats, ResourceLimitError, evolve, format_basis, probabilities

DEFAULT_CAP = 4096


def load_circuit(path):
    with path.open("rb") as source:
        data = source.read(65537)
    if len(data) > 65536:
        raise ValueError("Source exceeds 65536 bytes")
    match = re.fullmatch(r"\s*quantum\s+([A-Za-z_]\w*)\s*\{([^{}]*)\}\s*", data.decode("utf-8-sig"))
    if match is None:
        raise ValueError("Expected one named quantum block")
    parsed = parse(match[2], max_qubits=40, sparse=True)
    gates = tuple(
        (op, args[1], args[2], args[0]) if op == "cp" else (op, *args)
        for op, args in parsed["gates"]
    )
    return Circuit(parsed["n"], gates, match[1]), hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--support-cap", type=int, default=DEFAULT_CAP)
    parser.add_argument("--timeout", type=float, default=5.0, help="Evolution deadline in seconds")
    args = parser.parse_args()
    try:
        circuit, source_digest = load_circuit(args.source)
        stats = EvolutionStats()
        report = dict(source=args.source.name, source_sha256=source_digest,
                      qubits=circuit.qubits, gates=len(circuit.gates),
                      support_cap=args.support_cap, timeout_seconds=args.timeout)
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
