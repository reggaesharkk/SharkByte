"""Compare a connected 40-qubit, 33,554,432-support GHZ-family run to an exact oracle."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for _path in (str(ROOT), str(BENCHMARK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from frontier30 import load_circuit
import sparse_backend

QUBITS = 40
EXPANDED_QUBITS = 24
STATES = 1 << (EXPANDED_QUBITS + 1)
SUPPORT_CAP = STATES
MEMORY_BUDGET_BYTES = STATES * sparse_backend.ESTIMATED_BYTES_PER_AMPLITUDE
TOLERANCE = 1e-12
SOURCE = ROOT / "examples" / "connected_ghz40_33554432.sb"
CODE_PATHS = (
    "examples/connected_ghz40_33554432.sb",
    "tools/run_connected_ghz40_high_support.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
    "benchmarks/sb_quantum_benchmark/frontier30.py",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def expected_gates() -> tuple[tuple, ...]:
    return (("h", 0),) + tuple(("cx", q, q + 1) for q in range(QUBITS - 1)) + tuple(
        ("h", q) for q in range(EXPANDED_QUBITS)
    )


def graph_is_connected(width: int, gates: tuple[tuple, ...]) -> bool:
    adjacency = [set() for _ in range(width)]
    for gate in gates:
        if gate[0] == "cx":
            left, right = gate[1:3]
            adjacency[left].add(right)
            adjacency[right].add(left)
    seen = {0}
    pending = [0]
    while pending:
        for neighbor in adjacency[pending.pop()]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return len(seen) == width


def cirq_measurement_check(gates: tuple[tuple, ...], *, seed: int, repetitions: int) -> dict:
    qubits = cirq.LineQubit.range(QUBITS)
    circuit = cirq.Circuit()
    for op, *values in gates:
        if op == "h":
            operation = cirq.H(qubits[values[0]])
        elif op == "cx":
            operation = cirq.CNOT(qubits[values[0]], qubits[values[1]])
        else:
            raise ValueError(f"unexpected gate in Clifford circuit: {op}")
        circuit.append(operation, strategy=cirq.InsertStrategy.NEW)
    circuit.append(cirq.measure(*qubits, key="bits"), strategy=cirq.InsertStrategy.NEW)
    samples = cirq.CliffordSimulator(seed=seed).run(
        circuit, repetitions=repetitions
    ).measurements["bits"]
    tails = samples[:, EXPANDED_QUBITS:]
    coherent_tail = bool(np.all(tails == tails[:, :1]))
    branch_values = sorted({int(row[0]) for row in tails})
    passed = coherent_tail and branch_values == [0, 1]
    return {
        "status": "PASS" if passed else "FAIL",
        "method": "Cirq CliffordSimulator sampled computational-basis outcomes",
        "repetitions": repetitions,
        "seed": seed,
        "unexpanded_tail_qubits": QUBITS - EXPANDED_QUBITS,
        "tail_is_all_zero_or_all_one_each_shot": coherent_tail,
        "observed_tail_branches": branch_values,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--max-seconds", type=float, default=300.0)
    parser.add_argument("--cirq-seed", type=int, default=20261117)
    parser.add_argument("--cirq-repetitions", type=int, default=512)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Refusing to overwrite existing receipt: {output}")

    source_bytes = SOURCE.read_bytes()
    source_hash = sha256_bytes(source_bytes)
    circuit, parsed_hash = load_circuit(SOURCE)
    gates = expected_gates()
    if parsed_hash != source_hash or circuit.qubits != QUBITS or circuit.gates != gates:
        raise ValueError("parsed source differs from the frozen connected GHZ gate sequence")
    connected = graph_is_connected(circuit.qubits, circuit.gates)
    if not connected:
        raise ValueError("CX interaction graph is not connected")

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    cirq_started = time.perf_counter()
    cirq_check = cirq_measurement_check(
        gates, seed=args.cirq_seed, repetitions=args.cirq_repetitions
    )
    cirq_seconds = time.perf_counter() - cirq_started

    progress_file = args.progress_file.resolve() if args.progress_file else None

    def report_progress(phase: str, done: int, total: int, active: int) -> None:
        if progress_file is None:
            return
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        with progress_file.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"phase": phase, "gate_index": done,
                                     "gate_count": total, "active_states": active}) + "\n")
            stream.flush()

    stats = sparse_backend.EvolutionStats()
    started = time.perf_counter()
    state = sparse_backend.evolve(
        sparse_backend.Circuit(circuit.qubits, circuit.gates, "connected_ghz40_high_support"),
        support_cap=SUPPORT_CAP,
        memory_budget_bytes=MEMORY_BUDGET_BYTES,
        max_seconds=args.max_seconds,
        stats=stats,
        progress_callback=lambda done, total, active: report_progress(
            "evolving", done, total, active
        ),
    )
    evolution_seconds = time.perf_counter() - started
    report_progress("comparing_analytic_oracle", 0, len(state), len(state))

    low_mask = (1 << EXPANDED_QUBITS) - 1
    all_one_tail = (1 << (QUBITS - EXPANDED_QUBITS)) - 1
    amplitude = 1.0 / math.sqrt(STATES)
    max_amplitude_error = 0.0
    max_probability_error = 0.0
    branch_counts = {"zero_tail": 0, "one_tail": 0, "invalid_tail": 0}
    for basis, actual in state.items():
        low = basis & low_mask
        tail = basis >> EXPANDED_QUBITS
        if tail == 0:
            expected = complex(amplitude, 0.0)
            branch_counts["zero_tail"] += 1
        elif tail == all_one_tail:
            sign = -1.0 if low.bit_count() & 1 else 1.0
            expected = complex(sign * amplitude, 0.0)
            branch_counts["one_tail"] += 1
        else:
            expected = 0.0j
            branch_counts["invalid_tail"] += 1
        max_amplitude_error = max(max_amplitude_error, abs(actual - expected))
        max_probability_error = max(
            max_probability_error, abs(abs(actual) ** 2 - abs(expected) ** 2)
        )
    norm = math.fsum(abs(value) ** 2 for value in state.values())
    expected_count = 1 << (EXPANDED_QUBITS + 1)
    passed = (
        cirq_check["status"] == "PASS"
        and len(state) == stats.peak_support == expected_count == STATES
        and branch_counts == {"zero_tail": 1 << EXPANDED_QUBITS,
                              "one_tail": 1 << EXPANDED_QUBITS,
                              "invalid_tail": 0}
        and abs(norm - 1.0) <= TOLERANCE
        and max_amplitude_error <= TOLERANCE
        and max_probability_error <= TOLERANCE
    )

    identity = {
        "format": "sharkbyte-connected-ghz40-32m-v1",
        "source_sha256": source_hash,
        "qubits": circuit.qubits,
        "ordered_gates": gates,
        "analytic_formula": "uniform 2^-12.5 amplitudes on low-24 free bits with tail q24..q39 all zero or all one; the all-one tail has sign (-1)^popcount(low24)",
    }
    circuit_sha256 = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    report = {
        "status": "PASS" if passed else "FAIL",
        "claim_scope": "Connected 40-qubit GHZ-family sparse simulation with an exact analytical full-amplitude oracle; no dense 40-qubit statevector is computed.",
        "execution_id": circuit_sha256[:32],
        "circuit_sha256": circuit_sha256,
        "source_commit": source_commit,
        "source_path": SOURCE.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "source_gate_count": len(gates),
        "qubits": QUBITS,
        "interaction_graph_connected": connected,
        "entangling_edges": QUBITS - 1,
        "target_active_states": STATES,
        "sharkbyte_peak_active_states": stats.peak_support,
        "analytic_reference": {
            "status": "PASS" if passed else "FAIL",
            "type": "closed-form GHZ plus local-Hadamard amplitude formula",
            "compared_sparse_amplitudes": len(state),
            "max_complex_amplitude_error": max_amplitude_error,
            "max_probability_error": max_probability_error,
            "probability_sum": norm,
            "tolerance": TOLERANCE,
            "branch_counts": branch_counts,
        },
        "entanglement_witness": {
            "status": "PASS" if passed else "FAIL",
            "pre_local_unitary_state": "40-qubit GHZ prepared by H(0) and the connected CX chain",
            "local_unitaries": ["H(q) for q=0..23"],
            "all_nontrivial_bipartitions": {
                "schmidt_rank": 2,
                "schmidt_probabilities": [0.5, 0.5],
                "entropy_bits": 1.0,
                "proof": "For every nontrivial cut, the two GHZ branches are orthogonal on each side. The subsequent single-qubit Hadamards are local with respect to every cut and preserve these Schmidt coefficients.",
            },
        },
        "cirq_reference": cirq_check,
        "dense_40q_statevector": {
            "status": "NOT RUN",
            "reason": "A complex128 statevector for 2^40 basis states requires 16 TiB before simulator overhead.",
        },
        "timing_seconds": {
            "sharkbyte_sparse_evolution": evolution_seconds,
            "cirq_clifford_measurement_check": cirq_seconds,
        },
        "environment": {
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "cirq_core": cirq.__version__,
            "numpy": np.__version__,
            "support_cap": SUPPORT_CAP,
            "estimated_memory_budget_bytes": MEMORY_BUDGET_BYTES,
        },
        "code_sha256": {
            path: sha256_bytes((ROOT / path).read_bytes()) for path in CODE_PATHS
        },
    }
    report["receipt_sha256"] = sha256_bytes(json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8"))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "active_states": len(state),
                      "amplitude_error": max_amplitude_error, "norm": norm}))
    print(f"Receipt: {output}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
