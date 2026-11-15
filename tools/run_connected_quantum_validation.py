"""Compare connected SharkByte sparse circuits with a live Qiskit or Cirq statevector."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import math
import platform
from pathlib import Path
import sys
import tempfile
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for _path in (str(ROOT), str(BENCHMARK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from frontier30 import load_circuit  # noqa: E402
import sparse_backend  # noqa: E402
from validation.connected_quantum.corpus import (  # noqa: E402
    build_cases,
    corpus_sha256,
    graph_is_connected,
)


AMPLITUDE_TOLERANCE = 1e-10
PROBABILITY_MAX_TOLERANCE = 1e-10
PROBABILITY_L1_TOLERANCE = 1e-9
NORMALIZATION_TOLERANCE = 1e-10
DEFAULT_SUPPORT_CAP = 65_536
DEFAULT_MEMORY_BUDGET = 64 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60.0
CODE_PATHS = (
    "validation/connected_quantum/corpus.py",
    "tools/run_connected_quantum_validation.py",
    "benchmarks/sb_quantum_benchmark/quantum_frontend.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
    "benchmarks/sb_quantum_benchmark/frontier30.py",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _state_hash(state: np.ndarray) -> str:
    canonical = np.ascontiguousarray(state, dtype="<c16")
    return _sha256(canonical.tobytes(order="C"))


def _dense_state(sparse_state: dict[int, complex], width: int) -> np.ndarray:
    result = np.zeros(1 << width, dtype="<c16")
    for basis, amplitude in sparse_state.items():
        result[basis] = amplitude
    return result


def _state_metrics(reference: np.ndarray, actual: np.ndarray) -> dict:
    if reference.shape != actual.shape:
        return {
            "status": "FAIL",
            "reason": "statevector length mismatch",
            "reference_length": int(reference.size),
            "actual_length": int(actual.size),
        }
    overlap = np.vdot(reference, actual)
    phase = overlap / abs(overlap) if abs(overlap) else 1.0 + 0.0j
    aligned = actual * np.conjugate(phase)
    reference_probabilities = np.abs(reference) ** 2
    actual_probabilities = np.abs(actual) ** 2
    max_amplitude = float(np.max(np.abs(reference - aligned), initial=0.0))
    max_probability = float(np.max(
        np.abs(reference_probabilities - actual_probabilities), initial=0.0
    ))
    l1_probability = float(np.sum(
        np.abs(reference_probabilities - actual_probabilities), dtype=np.float64
    ))
    norm = math.fsum(float(value) for value in actual_probabilities)
    passed = (
        max_amplitude <= AMPLITUDE_TOLERANCE
        and max_probability <= PROBABILITY_MAX_TOLERANCE
        and l1_probability <= PROBABILITY_L1_TOLERANCE
        and abs(norm - 1.0) <= NORMALIZATION_TOLERANCE
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "basis_states_compared": int(reference.size),
        "overlap_magnitude": float(abs(overlap)),
        "global_phase_radians": float(math.atan2(float(phase.imag), float(phase.real))),
        "max_complex_amplitude_error_global_phase_aligned": max_amplitude,
        "max_probability_error": max_probability,
        "l1_probability_error": l1_probability,
        "actual_norm": norm,
        "actual_norm_error": abs(norm - 1.0),
    }


def _entanglement_witnesses(state: np.ndarray, width: int) -> dict[str, dict]:
    """Compute reduced-state Schmidt spectra for several explicit register cuts."""
    candidate_cuts = {
        "lower_half_vs_upper_half": list(range(max(1, width // 2))),
        "even_qubits_vs_odd_qubits": list(range(0, width, 2)),
        "q0_vs_rest": [0],
    }
    if width >= 4:
        candidate_cuts["outer_qubits_vs_middle"] = [0, width - 1]
    tensor = state.reshape((2,) * width)
    output = {}
    for name, subset in candidate_cuts.items():
        subset = sorted(set(subset))
        complement = [q for q in range(width) if q not in subset]
        axes_a = [width - 1 - q for q in subset]
        axes_b = [width - 1 - q for q in complement]
        matrix = np.transpose(tensor, axes_b + axes_a).reshape(
            1 << len(complement), 1 << len(subset)
        )
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        probabilities = [float(value * value) for value in singular_values]
        norm = math.fsum(probabilities)
        purity = math.fsum(value * value for value in probabilities)
        entropy = -math.fsum(
            value * math.log2(value) for value in probabilities if value > 0.0
        )
        output[name] = {
            "subset_qubits": subset,
            "complement_qubits": complement,
            # Cast explicitly: NumPy's scalar bool/int types are not JSON values.
            "schmidt_rank_at_1e-10": int(sum(bool(value > 1e-10) for value in singular_values)),
            "reduced_state_purity": purity,
            "linear_entropy": max(0.0, 1.0 - purity),
            "von_neumann_entropy_bits": entropy,
            "normalized_state": abs(norm - 1.0) <= NORMALIZATION_TOLERANCE,
            "entangled_across_cut": purity < 1.0 - 1e-8,
        }
    return output


def _gate_tuples(case: dict) -> tuple[tuple, ...]:
    return tuple(tuple(gate) for gate in case["gates"])


def _check_source(case: dict, gates: tuple[tuple, ...]) -> dict:
    raw = case["source"].encode("utf-8")
    actual_hash = _sha256(raw)
    if actual_hash != case["source_sha256"]:
        raise ValueError(f"{case['id']}: source SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="sharkbyte-connected-") as directory:
        source_path = Path(directory) / "circuit.sb"
        source_path.write_bytes(raw)
        circuit, loaded_hash = load_circuit(source_path)
    if loaded_hash != actual_hash:
        raise ValueError(f"{case['id']}: loader source hash mismatch")
    if circuit.qubits != case["width"] or circuit.gates != gates:
        raise ValueError(f"{case['id']}: parsed width or ordered gates differ from corpus")
    if len(gates) != case["prefix_gate_count"] * 2:
        raise ValueError(f"{case['id']}: gate sequence is not prefix followed by its inverse")
    if tuple(gates[case["prefix_gate_count"]:]) != _inverse(gates[:case["prefix_gate_count"]]):
        raise ValueError(f"{case['id']}: inverse gate sequence differs from the prefix inverse")
    return {"source_sha256": actual_hash, "ordered_gate_sequence_matches": True}


def _inverse(gates: tuple[tuple, ...]) -> tuple[tuple, ...]:
    inverse = []
    for gate in reversed(gates):
        if gate[0] == "cp":
            inverse.append(("cp", gate[1], gate[2], -gate[3]))
        elif gate[0] in ("rx", "ry", "rz"):
            inverse.append((gate[0], gate[1], -gate[2]))
        else:
            inverse.append(gate)
    return tuple(inverse)


def _qiskit_state(width: int, gates: tuple[tuple, ...]) -> tuple[np.ndarray, dict]:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    circuit = QuantumCircuit(width)
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            getattr(circuit, op)(gate[1])
        elif op == "cx":
            circuit.cx(gate[1], gate[2])
        elif op == "cp":
            circuit.cp(float(gate[3]), gate[1], gate[2])
        elif op in ("rx", "ry", "rz"):
            getattr(circuit, op)(float(gate[2]), gate[1])
        else:
            raise ValueError(f"Unsupported canonical gate: {op}")

    actual = []
    for item in circuit.data:
        operation = item.operation
        qubits = [circuit.find_bit(qubit).index for qubit in item.qubits]
        entry = {"op": operation.name, "qubits": qubits}
        if operation.name in ("cp", "rx", "ry", "rz"):
            entry["angle"] = float(operation.params[0])
        actual.append(entry)
    state = np.asarray(Statevector.from_instruction(circuit).data, dtype="<c16")
    return state, {"instruction_count": len(actual), "instruction_order": actual}


def _cirq_state(width: int, gates: tuple[tuple, ...]) -> tuple[np.ndarray, dict]:
    import cirq

    qubits = cirq.LineQubit.range(width)
    circuit = cirq.Circuit()
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            operation = {"h": cirq.H, "x": cirq.X, "z": cirq.Z}[op](qubits[gate[1]])
        elif op == "cx":
            operation = cirq.CNOT(qubits[gate[1]], qubits[gate[2]])
        elif op == "cp":
            operation = cirq.CZPowGate(exponent=float(gate[3]) / math.pi)(
                qubits[gate[1]], qubits[gate[2]]
            )
        elif op in ("rx", "ry", "rz"):
            operation = {"rx": cirq.rx, "ry": cirq.ry, "rz": cirq.rz}[op](
                float(gate[2])
            )(qubits[gate[1]])
        else:
            raise ValueError(f"Unsupported canonical gate: {op}")
        circuit.append(operation, strategy=cirq.InsertStrategy.NEW)

    operations = list(circuit.all_operations())
    if len(operations) != len(gates):
        raise ValueError("Cirq circuit instruction count differs from corpus")
    for expected, operation in zip(gates, operations):
        expected_indices = list(expected[1:3]) if expected[0] in ("cx", "cp") else [expected[1]]
        actual_indices = [qubit.x for qubit in operation.qubits]
        if actual_indices != expected_indices:
            raise ValueError("Cirq circuit changed gate qubit order")
    state = cirq.Simulator(dtype=np.complex128).simulate(
        circuit, qubit_order=qubits[::-1]
    ).final_state_vector
    return np.asarray(state, dtype="<c16"), {
        "instruction_count": len(operations),
        "instruction_order_and_qubits_match": True,
        "qubit_order": "q0 is least-significant basis-index bit",
    }


def _reference_state(backend: str, width: int,
                    gates: tuple[tuple, ...]) -> tuple[np.ndarray, dict, float]:
    started = time.perf_counter()
    if backend == "qiskit":
        state, metadata = _qiskit_state(width, gates)
    else:
        state, metadata = _cirq_state(width, gates)
    return state, metadata, time.perf_counter() - started


def _run_sparse(width: int, gates: tuple[tuple, ...], *, support_cap: int,
                memory_budget_bytes: int, timeout_seconds: float) -> tuple[np.ndarray, dict, float]:
    circuit = sparse_backend.Circuit(width, gates, "connected-validation")
    stats = sparse_backend.EvolutionStats()
    started = time.perf_counter()
    state = sparse_backend.evolve(
        circuit,
        support_cap=support_cap,
        memory_budget_bytes=memory_budget_bytes,
        max_seconds=timeout_seconds,
        stats=stats,
    )
    elapsed = time.perf_counter() - started
    return _dense_state(state, width), {
        "final_support": len(state),
        "peak_support": stats.peak_support,
        "peak_gate_index": stats.peak_gate_index,
        "evolution_seconds": elapsed,
    }, elapsed


def _code_hashes() -> dict[str, str]:
    return {
        path: _sha256((ROOT / path).read_bytes())
        for path in CODE_PATHS
    }


def _run_case(case: dict, backend: str, *, support_cap: int,
              memory_budget_bytes: int, timeout_seconds: float,
              vectors: dict[str, np.ndarray]) -> dict:
    gates = _gate_tuples(case)
    width = case["width"]
    prefix_count = case["prefix_gate_count"]
    prefix = gates[:prefix_count]
    source_check = _check_source(case, gates)
    if not graph_is_connected(width, case["entangling_edges"]):
        raise ValueError(f"{case['id']}: two-qubit interaction graph is disconnected")

    prefix_ref, prefix_metadata, prefix_reference_seconds = _reference_state(
        backend, width, prefix
    )
    prefix_sparse, prefix_sparse_metadata, _ = _run_sparse(
        width, prefix, support_cap=support_cap,
        memory_budget_bytes=memory_budget_bytes,
        timeout_seconds=timeout_seconds,
    )
    final_ref, final_metadata, final_reference_seconds = _reference_state(
        backend, width, gates
    )
    final_sparse, final_sparse_metadata, _ = _run_sparse(
        width, gates, support_cap=support_cap,
        memory_budget_bytes=memory_budget_bytes,
        timeout_seconds=timeout_seconds,
    )

    prefix_metrics = _state_metrics(prefix_ref, prefix_sparse)
    final_metrics = _state_metrics(final_ref, final_sparse)
    entanglement = _entanglement_witnesses(prefix_ref, width)
    expectation = case["entanglement_expectation"]
    if expectation == "nonfactorizing-across-tested-cuts":
        entanglement_passed = all(
            item["entangled_across_cut"] and item["normalized_state"]
            for item in entanglement.values()
        )
    elif expectation == "separable-product-control":
        entanglement_passed = all(
            not item["entangled_across_cut"]
            and abs(item["reduced_state_purity"] - 1.0) <= 1e-10
            and item["normalized_state"]
            for item in entanglement.values()
        )
    else:
        entanglement_passed = True
    vacuum_probability = float(abs(final_ref[0]) ** 2)
    inverse_max_other_amplitude = float(
        np.max(np.abs(final_ref[1:]), initial=0.0)
    )
    inverse_passed = (
        abs(vacuum_probability - 1.0) <= NORMALIZATION_TOLERANCE
        and inverse_max_other_amplitude <= AMPLITUDE_TOLERANCE
    )

    prefix_key = case["id"] + "__prefix"
    final_key = case["id"] + "__inverse"
    vectors[prefix_key] = prefix_ref
    vectors[final_key] = final_ref
    result = {
        "id": case["id"],
        "kind": case["kind"],
        "entanglement_expectation": expectation,
        "width": width,
        "seed": case["seed"],
        "prefix_gate_count": prefix_count,
        "gate_count": len(gates),
        "connected_interaction_graph": True,
        "interaction_edges": len(case["entangling_edges"]),
        "source": case["source"],
        **source_check,
        "prefix_reference": {
            "backend_metadata": prefix_metadata,
            "state_sha256": _state_hash(prefix_ref),
            "seconds": prefix_reference_seconds,
        },
        "prefix_sparse": {
            **prefix_sparse_metadata,
            "state_sha256": _state_hash(prefix_sparse),
        },
        "prefix_comparison": prefix_metrics,
        "prefix_entanglement": {
            "status": "PASS" if entanglement_passed else "FAIL",
            "classification": (
                "NONFACTORIZING_ACROSS_TESTED_CUTS"
                if expectation == "nonfactorizing-across-tested-cuts"
                and entanglement_passed else
                "SEPARABLE_ACROSS_TESTED_CUTS"
                if expectation == "separable-product-control"
                and entanglement_passed else
                "MEASURED_NO_REQUIRED_CLASSIFICATION"
                if expectation == "record-without-required-classification" else
                "FAIL"
            ),
            "witnesses": entanglement,
        },
        "inverse_reference": {
            "backend_metadata": final_metadata,
            "state_sha256": _state_hash(final_ref),
            "seconds": final_reference_seconds,
            "vacuum_probability": vacuum_probability,
            "maximum_nonvacuum_amplitude": inverse_max_other_amplitude,
            "inverse_identity_status": "PASS" if inverse_passed else "FAIL",
        },
        "inverse_sparse": {
            **final_sparse_metadata,
            "state_sha256": _state_hash(final_sparse),
        },
        "inverse_comparison": final_metrics,
    }
    result["status"] = (
        "PASS" if prefix_metrics["status"] == "PASS"
        and final_metrics["status"] == "PASS"
        and entanglement_passed
        and inverse_passed else "FAIL"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("qiskit", "cirq"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--support-cap", type=int, default=DEFAULT_SUPPORT_CAP)
    parser.add_argument("--memory-budget-mib", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()
    output = args.output.resolve()
    arrays_path = output.with_suffix(".states.npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or arrays_path.exists():
        parser.error(f"Refusing to overwrite an existing receipt or state archive: {output}")

    cases = build_cases()
    vectors: dict[str, np.ndarray] = {}
    case_reports = []
    for case in cases:
        try:
            report = _run_case(
                case, args.backend, support_cap=args.support_cap,
                memory_budget_bytes=args.memory_budget_mib * 1024 * 1024,
                timeout_seconds=args.timeout_seconds, vectors=vectors,
            )
        except Exception as exc:  # Keep an explicit failure record for any counterexample.
            report = {
                "id": case["id"], "kind": case["kind"], "width": case["width"],
                "seed": case["seed"], "source": case["source"],
                "source_sha256": case["source_sha256"],
                "status": "FAIL", "error_type": type(exc).__name__,
                "error": str(exc),
            }
        case_reports.append(report)
        print(f"{report['status']} {report['id']}")

    np.savez(arrays_path, **vectors)
    try:
        library = version("qiskit" if args.backend == "qiskit" else "cirq-core")
    except Exception:
        library = "UNKNOWN"
    failed = [case["id"] for case in case_reports if case["status"] != "PASS"]
    receipt = {
        "schema": 1,
        "status": "PASS" if not failed and len(case_reports) == len(cases) else "FAIL",
        "backend": args.backend,
        "reference_library_version": library,
        "numpy_version": np.__version__,
        "python_version": sys.version,
        "host": {
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "corpus_sha256": corpus_sha256(cases),
        "corpus_cases": len(cases),
        "randomized_connected_cases": sum(
            case["kind"] == "random-connected" for case in cases
        ),
        "adversarial_cases": sum(
            case["kind"].startswith("adversarial") for case in cases
        ),
        "widths": sorted({case["width"] for case in cases}),
        "support_cap": args.support_cap,
        "memory_budget_bytes": args.memory_budget_mib * 1024 * 1024,
        "timeout_seconds_per_evolution": args.timeout_seconds,
        "tolerances": {
            "phase_aligned_amplitude_max": AMPLITUDE_TOLERANCE,
            "probability_max": PROBABILITY_MAX_TOLERANCE,
            "probability_l1": PROBABILITY_L1_TOLERANCE,
            "normalization": NORMALIZATION_TOLERANCE,
        },
        "code_sha256": _code_hashes(),
        "state_archive": {
            "file": arrays_path.name,
            "sha256": _sha256(arrays_path.read_bytes()),
            "vectors": len(vectors),
        },
        "failed_cases": failed,
        "cases": case_reports,
    }
    receipt["receipt_sha256"] = _sha256(_canonical(receipt))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"{receipt['status']} {args.backend}: {len(cases) - len(failed)}/{len(cases)} cases")
    print(f"Receipt: {output}")
    print(f"State archive: {arrays_path}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
