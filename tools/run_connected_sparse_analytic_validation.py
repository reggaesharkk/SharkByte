"""Validate connected 20-40-qubit GHZ circuits against a closed-form oracle."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for _path in (str(ROOT), str(BENCHMARK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from frontier30 import load_circuit  # noqa: E402
import sparse_backend  # noqa: E402
from validation.connected_quantum.corpus import (  # noqa: E402
    analytic_entangled_ghz_state,
    analytic_ghz_state,
    build_sparse_analytic_cases,
    graph_is_connected,
)


TOLERANCE = 1e-10
SUPPORT_CAP = 16
MEMORY_BUDGET_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 15.0
CODE_PATHS = (
    "validation/connected_quantum/corpus.py",
    "tools/run_connected_sparse_analytic_validation.py",
    "benchmarks/sb_quantum_benchmark/quantum_frontend.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
    "benchmarks/sb_quantum_benchmark/frontier30.py",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _state_hash(state: dict[int, complex]) -> str:
    body = b"".join(
        struct.pack("<Qdd", basis, amplitude.real, amplitude.imag)
        for basis, amplitude in sorted(state.items())
    )
    return _sha256(body)


def _evaluate(case: dict) -> dict:
    raw = case["source"].encode("utf-8")
    source_hash = _sha256(raw)
    if source_hash != case["source_sha256"]:
        raise ValueError("source hash mismatch")
    with __import__("tempfile").TemporaryDirectory(prefix="sharkbyte-analytic-") as directory:
        path = Path(directory) / "circuit.sb"
        path.write_bytes(raw)
        circuit, loaded_hash = load_circuit(path)
    expected_gates = tuple(tuple(gate) for gate in case["gates"])
    if loaded_hash != source_hash or circuit.qubits != case["width"]:
        raise ValueError("source identity or register width mismatch")
    if circuit.gates != expected_gates:
        raise ValueError("parsed ordered gate list differs from the exact source corpus")
    if not graph_is_connected(case["width"], case["entangling_edges"]):
        raise ValueError("interaction graph is not connected")

    entangled_count = case["entangled_ghz_gate_count"]
    ghz_stats = sparse_backend.EvolutionStats()
    ghz_started = time.perf_counter()
    entangled_actual = sparse_backend.evolve(
        sparse_backend.Circuit(
            case["width"], circuit.gates[:entangled_count], case["id"] + "-ghz"
        ),
        support_cap=SUPPORT_CAP,
        memory_budget_bytes=MEMORY_BUDGET_BYTES,
        max_seconds=TIMEOUT_SECONDS,
        stats=ghz_stats,
    )
    ghz_elapsed = time.perf_counter() - ghz_started
    entangled_expected = analytic_entangled_ghz_state(case)
    ghz_bases = set(entangled_actual) | set(entangled_expected)
    ghz_error = max(
        (abs(entangled_actual.get(basis, 0.0j) - entangled_expected.get(basis, 0.0j))
         for basis in ghz_bases),
        default=0.0,
    )
    ghz_passed = (
        entangled_actual.keys() == entangled_expected.keys()
        and ghz_error <= TOLERANCE
        and ghz_stats.peak_support <= SUPPORT_CAP
    )

    stats = sparse_backend.EvolutionStats()
    started = time.perf_counter()
    actual = sparse_backend.evolve(
        circuit, support_cap=SUPPORT_CAP,
        memory_budget_bytes=MEMORY_BUDGET_BYTES,
        max_seconds=TIMEOUT_SECONDS, stats=stats,
    )
    elapsed = time.perf_counter() - started
    expected = analytic_ghz_state(case)
    bases = set(actual) | set(expected)
    max_amplitude_error = max(
        (abs(actual.get(basis, 0.0j) - expected.get(basis, 0.0j))
         for basis in bases),
        default=0.0,
    )
    max_probability_error = max(
        (abs(abs(actual.get(basis, 0.0j)) ** 2
             - abs(expected.get(basis, 0.0j)) ** 2)
         for basis in bases),
        default=0.0,
    )
    norm = math.fsum(abs(amplitude) ** 2 for amplitude in actual.values())
    final_passed = (
        actual.keys() == expected.keys()
        and max_amplitude_error <= TOLERANCE
        and max_probability_error <= TOLERANCE
        and abs(norm - 1.0) <= TOLERANCE
        and stats.peak_support <= SUPPORT_CAP
    )
    passed = ghz_passed and final_passed
    return {
        "id": case["id"],
        "status": "PASS" if passed else "FAIL",
        "width": case["width"],
        "gate_count": len(circuit.gates),
        "connected_interaction_graph": True,
        "entangling_edges": len(case["entangling_edges"]),
        "source": case["source"],
        "source_sha256": source_hash,
        "reference_method": case["reference_method"],
        "controlled_phase_angles": case["controlled_phase_angles"],
        "rz_angles": case["rz_angles"],
        "exact_relative_phase_radians": case["exact_relative_phase"],
        "entangled_ghz_checkpoint": {
            "gate_count": entangled_count,
            "populated_states": len(entangled_actual),
            "peak_support": ghz_stats.peak_support,
            "evolution_seconds": ghz_elapsed,
            "maximum_complex_amplitude_error": ghz_error,
            "state_sha256": _state_hash(entangled_actual),
            "every_nontrivial_bipartition": {
                "status": "PASS" if ghz_passed else "FAIL",
                "schmidt_rank": 2,
                "schmidt_probabilities": [0.5, 0.5],
                "reduced_state_purity": 0.5,
                "entropy_bits": 1.0,
                "reason": (
                    "The two phase-GHZ branches differ on every nonempty proper "
                    "subset and its complement, leaving two orthogonal Schmidt terms."
                ),
            },
        },
        "final_interference_checkpoint": {
            "status": "PASS" if final_passed else "FAIL",
            "populated_states": len(actual),
            "peak_support": stats.peak_support,
        },
        "sparse_populated_states": len(actual),
        "sparse_peak_support": stats.peak_support,
        "sparse_peak_gate_index": stats.peak_gate_index,
        "sparse_evolution_seconds": elapsed,
        "maximum_complex_amplitude_error": max_amplitude_error,
        "maximum_probability_error": max_probability_error,
        "normalization": norm,
        "state_sha256": _state_hash(actual),
        "expected_nonzero_amplitudes": [
            {
                "basis_index": basis,
                "real": value.real,
                "imag": value.imag,
                "probability": abs(value) ** 2,
            }
            for basis, value in sorted(expected.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Refusing to overwrite existing receipt: {output}")

    cases = build_sparse_analytic_cases()
    rows = []
    for case in cases:
        try:
            row = _evaluate(case)
        except Exception as exc:
            row = {
                "id": case["id"], "width": case["width"], "status": "FAIL",
                "source": case["source"], "source_sha256": case["source_sha256"],
                "error_type": type(exc).__name__, "error": str(exc),
            }
        rows.append(row)
        print(f"{row['status']} {row['id']}")

    failed = [row["id"] for row in rows if row["status"] != "PASS"]
    receipt = {
        "schema": 1,
        "status": "PASS" if not failed else "FAIL",
        "reference_type": "exact analytical closed-form statevector; no dense simulation claimed",
        "python_version": sys.version,
        "host": {
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "support_cap": SUPPORT_CAP,
        "memory_budget_bytes": MEMORY_BUDGET_BYTES,
        "timeout_seconds_per_case": TIMEOUT_SECONDS,
        "amplitude_probability_normalization_tolerance": TOLERANCE,
        "code_sha256": {
            path: _sha256((ROOT / path).read_bytes())
            for path in CODE_PATHS
        },
        "failed_cases": failed,
        "cases": rows,
    }
    receipt["receipt_sha256"] = _sha256(_canonical(receipt))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"{receipt['status']}: analytical connected sparse suite {len(rows) - len(failed)}/{len(rows)}")
    print(f"Receipt: {output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
