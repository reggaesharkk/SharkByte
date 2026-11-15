"""Reproducible SharkByte vs live Qiskit Statevector validation.

This code consumes the public SharkByte parser and simulator without modifying
or enabling any production or native execution path. Circuits are rendered
once as SharkByte source, parsed by SharkByte, and then replayed instruction by
instruction in Qiskit. Statevector.from_instruction performs the reference run.
"""
from __future__ import annotations

import cmath
import hashlib
import importlib.metadata
import json
import math
import platform
import random
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for _path in (str(ROOT), str(BENCHMARK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from sharkbyte_alpha import cli, quantum  # noqa: E402
from frontier30 import load_circuit  # noqa: E402
import sparse_backend  # noqa: E402

MASTER_SEED = 2026111500
RANDOM_CIRCUIT_COUNT = 120
ANGLE_LIMIT = 4.0 * math.pi
AMPLITUDE_TOLERANCE = 1e-10
PROBABILITY_MAX_TOLERANCE = 1e-10
PROBABILITY_L1_TOLERANCE = 1e-9
NORMALIZATION_TOLERANCE = 1e-10
SPARSE_AMPLITUDE_TOLERANCE = 1e-10
SPARSE_PROBABILITY_TOLERANCE = 1e-9
SUPPORTED_GATES = ("h", "x", "z", "cx", "cp", "rx", "ry", "rz")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _angle(rng: random.Random) -> float:
    return rng.uniform(-ANGLE_LIMIT, ANGLE_LIMIT)


def _source_angle(value: float) -> str:
    # Expand Python's shortest round-trip representation to decimal notation;
    # SharkByte's working grammar rejects exponents.
    return format(Decimal(repr(float(value))), "f")


def _random_gate(name: str, rng: random.Random, qubits: int) -> tuple:
    if name in ("h", "x", "z"):
        return (name, rng.randrange(qubits))
    if name == "cx":
        control, target = rng.sample(range(qubits), 2)
        return (name, control, target)
    if name == "cp":
        control, target = rng.sample(range(qubits), 2)
        return (name, control, target, _angle(rng))
    return (name, rng.randrange(qubits), _angle(rng))


def render_program(qubits: int, gates: list[tuple] | tuple[tuple, ...], seed: int) -> str:
    """Render canonical input accepted by SharkByte's documented parser."""
    lines = [f"qubits {qubits};", "shots 1;", f"seed {seed};"]
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            lines.append(f"{op} {gate[1]};")
        elif op == "cx":
            lines.append(f"cx {gate[1]} {gate[2]};")
        elif op == "cp":
            lines.append(f"cp {_source_angle(gate[3])} {gate[1]} {gate[2]};")
        else:
            lines.append(f"{op} {_source_angle(gate[2])} {gate[1]};")
    lines.append("measure_all;")
    return "\n".join(lines) + "\n"


def generate_circuit(seed: int) -> tuple[str, int, list[tuple]]:
    """Create one seeded circuit with every supported gate and varied ordering."""
    rng = random.Random(seed)
    qubits = rng.randint(2, 6)
    gates = [_random_gate(name, rng, qubits) for name in SUPPORTED_GATES]
    gates.extend(_random_gate(rng.choice(SUPPORTED_GATES), rng, qubits)
                 for _ in range(rng.randint(10, 22)))
    rng.shuffle(gates)
    return render_program(qubits, gates, seed), qubits, gates


def _tuple_descriptors(gates: list[tuple] | tuple[tuple, ...]) -> list[dict]:
    """Describe the generator's independent circuit IR, before parsing source."""
    result = []
    for gate in gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            result.append({"op": op, "qubits": [gate[1]]})
        elif op == "cx":
            result.append({"op": op, "qubits": [gate[1], gate[2]]})
        elif op == "cp":
            result.append({"op": op, "qubits": [gate[1], gate[2]], "angle": float(gate[3])})
        else:
            result.append({"op": op, "qubits": [gate[1]], "angle": float(gate[2])})
    return result


def _source_descriptors(parsed: dict) -> list[dict]:
    result = []
    for op, args in parsed["gates"]:
        if op in ("h", "x", "z", "cx"):
            result.append({"op": op, "qubits": list(args)})
        elif op == "cp":
            angle, control, target = args
            result.append({"op": op, "qubits": [control, target], "angle": float(angle)})
        else:
            angle, target = args
            result.append({"op": op, "qubits": [target], "angle": float(angle)})
    return result


def _build_qiskit(parsed: dict, canonical_gates: list[tuple] | tuple[tuple, ...]):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    circuit = QuantumCircuit(parsed["n"])
    for gate in canonical_gates:
        op = gate[0]
        if op in ("h", "x", "z"):
            getattr(circuit, op)(gate[1])
        elif op == "cx":
            circuit.cx(gate[1], gate[2])
        elif op == "cp":
            circuit.cp(float(gate[3]), gate[1], gate[2])
        else:
            getattr(circuit, op)(float(gate[2]), gate[1])
    return circuit, Statevector.from_instruction(circuit).data


def _qiskit_descriptors(circuit) -> list[dict]:
    result = []
    for instruction in circuit.data:
        operation = instruction.operation
        qubits = [circuit.find_bit(qubit).index for qubit in instruction.qubits]
        item = {"op": operation.name, "qubits": qubits}
        if operation.name in ("cp", "rx", "ry", "rz"):
            item["angle"] = float(operation.params[0])
        result.append(item)
    return result


def _state_metrics(expected, actual) -> dict:
    if len(expected) != len(actual):
        return {"basis_states_compared": min(len(expected), len(actual)),
                "status": "FAIL", "reason": "statevector length mismatch"}
    overlap = sum(complex(a).conjugate() * complex(b)
                  for a, b in zip(expected, actual))
    phase = overlap / abs(overlap) if abs(overlap) > 0.0 else 1.0 + 0.0j
    aligned = [complex(b) * phase.conjugate() for b in actual]
    errors = [abs(complex(a) - b) for a, b in zip(expected, aligned)]
    return {
        "basis_states_compared": len(expected),
        "overlap_magnitude": abs(overlap),
        "global_phase_radians": math.atan2(phase.imag, phase.real),
        "max_complex_amplitude_error_global_phase_aligned": max(errors, default=0.0),
        "l2_complex_amplitude_error_global_phase_aligned": math.sqrt(math.fsum(e * e for e in errors)),
    }


def _probabilities(state) -> list[float]:
    return [float(abs(complex(amplitude)) ** 2) for amplitude in state]


def _norm_error(state) -> tuple[float, float]:
    norm = math.fsum(_probabilities(state))
    return norm, abs(norm - 1.0)


def _evaluate_source(source: str, expected_seed: int,
                     canonical_gates: list[tuple] | tuple[tuple, ...],
                     *, include_vectors: bool = True) -> dict:
    """Execute one source circuit in dense SharkByte, sparse SharkByte and Qiskit."""
    raw = source.encode("utf-8")
    parsed = cli.parse_quantum(source)
    if parsed["seed"] != expected_seed:
        raise AssertionError("parsed seed differs from requested seed")
    qiskit_circuit, qiskit_state = _build_qiskit(parsed, canonical_gates)
    dense_state = quantum.simulate(parsed)
    sparse_source = "quantum validation {\n" + source + "\n}\n"
    sparse_raw = sparse_source.encode("utf-8")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "validation.sb"
        path.write_bytes(sparse_raw)
        sparse_circuit, sparse_source_hash = load_circuit(path)
    sparse_state = sparse_backend.evolve(sparse_circuit)
    sparse_dense = [sparse_state.get(index, 0.0j) for index in range(1 << parsed["n"])]

    source_gates = _source_descriptors(parsed)
    generated_gates = _tuple_descriptors(canonical_gates)
    qiskit_gates = _qiskit_descriptors(qiskit_circuit)
    dense_prob = _probabilities(dense_state)
    qiskit_prob = _probabilities(qiskit_state)
    sparse_prob = _probabilities(sparse_dense)
    probability_errors = [abs(a - b) for a, b in zip(dense_prob, qiskit_prob)]
    sparse_probability_errors = [abs(a - b) for a, b in zip(dense_prob, sparse_prob)]
    dense_norm, dense_norm_error = _norm_error(dense_state)
    qiskit_norm, qiskit_norm_error = _norm_error(qiskit_state)
    sparse_norm, sparse_norm_error = _norm_error(sparse_dense)
    amplitude = _state_metrics(dense_state, qiskit_state)
    sparse_amplitude = _state_metrics(dense_state, sparse_dense)
    gate_sequence_match = source_gates == generated_gates == qiskit_gates
    checks = {
        "parsed_and_qiskit_sequences_match_canonical_source": gate_sequence_match,
        "frontier_source_matches_canonical": (
            sparse_source_hash == _sha256(sparse_raw)
            and sparse_circuit.qubits == parsed["n"]
            and _tuple_descriptors(sparse_circuit.gates) == generated_gates
        ),
        "global_phase_aligned_amplitudes": amplitude.get("max_complex_amplitude_error_global_phase_aligned", math.inf) <= AMPLITUDE_TOLERANCE,
        "probabilities": max(probability_errors, default=0.0) <= PROBABILITY_MAX_TOLERANCE
            and math.fsum(probability_errors) <= PROBABILITY_L1_TOLERANCE,
        "state_normalization": max(dense_norm_error, qiskit_norm_error, sparse_norm_error) <= NORMALIZATION_TOLERANCE,
        "sparse_dense_amplitudes": sparse_amplitude.get("max_complex_amplitude_error_global_phase_aligned", math.inf) <= SPARSE_AMPLITUDE_TOLERANCE,
        "sparse_dense_probabilities": max(sparse_probability_errors, default=0.0) <= SPARSE_PROBABILITY_TOLERANCE,
    }
    result = {
        "seed": parsed["seed"],
        "qubits": parsed["n"],
        "gate_count": len(parsed["gates"]),
        "source_sha256": _sha256(raw),
        "gate_sequence_sha256": _sha256(_canonical(source_gates)),
        "generated_gate_sequence_sha256": _sha256(_canonical(generated_gates)),
        "qiskit_gate_sequence_sha256": _sha256(_canonical(qiskit_gates)),
        "source": source,
        "frontier_source": sparse_source,
        "frontier_source_sha256": sparse_source_hash,
        "parsed_gate_sequence": source_gates,
        "generated_gate_sequence": generated_gates,
        "qiskit_gate_sequence": qiskit_gates,
        "gate_sequence_match": gate_sequence_match,
        "amplitude_comparison": amplitude,
        "probability_comparison": {
            "max_absolute_error": max(probability_errors, default=0.0),
            "l1_error": math.fsum(probability_errors),
        },
        "normalization": {
            "sharkbyte_dense_norm": dense_norm,
            "qiskit_norm": qiskit_norm,
            "sharkbyte_sparse_norm": sparse_norm,
            "max_norm_error_from_one": max(dense_norm_error, qiskit_norm_error, sparse_norm_error),
        },
        "sparse_dense_comparison": {
            "max_complex_amplitude_error_global_phase_aligned": sparse_amplitude.get("max_complex_amplitude_error_global_phase_aligned", math.inf),
            "max_probability_error": max(sparse_probability_errors, default=0.0),
            "l1_probability_error": math.fsum(sparse_probability_errors),
        },
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    if include_vectors:
        result["basis_order"] = "integer basis index; qubit 0 is least-significant bit; labels are MSB-left"
        result["probabilities_sharkbyte"] = dense_prob
        result["probabilities_qiskit"] = qiskit_prob
        result["amplitudes_sharkbyte"] = [[complex(x).real, complex(x).imag] for x in dense_state]
        result["amplitudes_qiskit"] = [[complex(x).real, complex(x).imag] for x in qiskit_state]
    return result


def _summarize_cases(cases: list[dict]) -> dict:
    return {
        "circuits": len(cases),
        "basis_states_compared": sum(case["amplitude_comparison"]["basis_states_compared"] for case in cases),
        "max_global_phase_aligned_amplitude_error": max(
            (case["amplitude_comparison"]["max_complex_amplitude_error_global_phase_aligned"] for case in cases), default=0.0),
        "max_probability_error": max((case["probability_comparison"]["max_absolute_error"] for case in cases), default=0.0),
        "max_l1_probability_error": max((case["probability_comparison"]["l1_error"] for case in cases), default=0.0),
        "max_norm_error": max((case["normalization"]["max_norm_error_from_one"] for case in cases), default=0.0),
        "max_sparse_dense_amplitude_error": max((case["sparse_dense_comparison"]["max_complex_amplitude_error_global_phase_aligned"] for case in cases), default=0.0),
        "max_sparse_dense_probability_error": max((case["sparse_dense_comparison"]["max_probability_error"] for case in cases), default=0.0),
        "passed": sum(case["status"] == "PASS" for case in cases),
        "failed": sum(case["status"] != "PASS" for case in cases),
    }


def validate_randomized() -> dict:
    cases = []
    reproducibility = True
    gate_coverage: set[str] = set()
    for index in range(RANDOM_CIRCUIT_COUNT):
        seed = MASTER_SEED + index
        source, qubits, gates = generate_circuit(seed)
        duplicate, duplicate_qubits, duplicate_gates = generate_circuit(seed)
        reproducibility = (reproducibility and source == duplicate
                           and qubits == duplicate_qubits and gates == duplicate_gates)
        case = _evaluate_source(source, seed, gates)
        gate_coverage.update(gate["op"] for gate in case["parsed_gate_sequence"])
        cases.append(case)
    summary = _summarize_cases(cases)
    summary["master_seed"] = MASTER_SEED
    summary["exact_seeds"] = [MASTER_SEED + i for i in range(RANDOM_CIRCUIT_COUNT)]
    summary["gate_coverage"] = sorted(gate_coverage)
    summary["all_supported_gates_covered"] = gate_coverage == set(SUPPORTED_GATES)
    summary["deterministic_replay"] = reproducibility
    status = (summary["failed"] == 0 and summary["all_supported_gates_covered"]
              and reproducibility and summary["circuits"] >= 100)
    return {"status": "PASS" if status else "FAIL", "summary": summary, "cases": cases}


def _inverse_gates(gate: tuple) -> list[tuple]:
    op = gate[0]
    if op == "cp":
        return [gate, ("cp", gate[1], gate[2], -float(gate[3]))]
    if op in ("rx", "ry", "rz"):
        return [gate, (op, gate[1], -float(gate[2]))]
    return [gate, gate]


def validate_gate_inverses() -> dict:
    prefix = [("h", 0), ("rx", 1, 0.31), ("ry", 2, -0.52),
              ("cx", 0, 2), ("cp", 1, 0, 0.73)]
    targets = [("h", 2), ("x", 1), ("z", 0), ("cx", 2, 1),
               ("cp", 0, 2, -0.91), ("rx", 0, 0.82),
               ("ry", 1, -1.13), ("rz", 2, 2.01)]
    checks = []
    seed = MASTER_SEED + RANDOM_CIRCUIT_COUNT
    for name, target in zip(SUPPORTED_GATES, targets):
        prefix_source = render_program(3, prefix, seed)
        parsed_prefix = cli.parse_quantum(prefix_source)
        initial = quantum.simulate(parsed_prefix)
        _, qiskit_initial = _build_qiskit(parsed_prefix, prefix)
        source = render_program(3, prefix + _inverse_gates(target), seed)
        operations = prefix + _inverse_gates(target)
        result = _evaluate_source(source, seed, operations, include_vectors=False)
        parsed_final = cli.parse_quantum(source)
        final_dense = quantum.simulate(parsed_final)
        _, final_qiskit = _build_qiskit(parsed_final, operations)
        dense_return = _state_metrics(initial, final_dense)
        qiskit_return = _state_metrics(qiskit_initial, final_qiskit)
        passed = (result["status"] == "PASS"
                  and dense_return["max_complex_amplitude_error_global_phase_aligned"] <= AMPLITUDE_TOLERANCE
                  and qiskit_return["max_complex_amplitude_error_global_phase_aligned"] <= AMPLITUDE_TOLERANCE)
        checks.append({"gate": name, "status": "PASS" if passed else "FAIL",
                       "seed": seed, "source": result["source"],
                       "parsed_gate_sequence": result["parsed_gate_sequence"],
                       "generated_gate_sequence": result["generated_gate_sequence"],
                       "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                       "source_sha256": result["source_sha256"],
                       "sharkbyte_return_error": dense_return["max_complex_amplitude_error_global_phase_aligned"],
                       "qiskit_return_error": qiskit_return["max_complex_amplitude_error_global_phase_aligned"],
                       "qiskit_vs_sharkbyte_error": result["amplitude_comparison"]["max_complex_amplitude_error_global_phase_aligned"]})
    return {"status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
            "checks": checks, "summary": {"inverse_pairs": len(checks)}}


def validate_interference() -> dict:
    cases = []
    examples = [
        ("hadamard_cancellation", 1, [("h", 0), ("h", 0)], {0: 1.0}),
        ("phase_flip_interference", 1, [("h", 0), ("z", 0), ("h", 0)], {1: 1.0}),
        ("controlled_phase_interference", 2,
         [("h", 0), ("h", 1), ("cp", 0, 1, math.pi / 3), ("h", 0)],
         {0: 0.5, 1: 0.0, 2: 0.375, 3: 0.125}),
    ]
    seed = MASTER_SEED + RANDOM_CIRCUIT_COUNT + 20
    for name, qubits, gates, expected in examples:
        source = render_program(qubits, gates, seed)
        result = _evaluate_source(source, seed, gates, include_vectors=False)
        parsed = cli.parse_quantum(source)
        dense_prob = _probabilities(quantum.simulate(parsed))
        _, qiskit_state = _build_qiskit(parsed, gates)
        qiskit_prob = _probabilities(qiskit_state)
        expected_dense = max(abs(dense_prob[index] - value) for index, value in expected.items())
        expected_qiskit = max(abs(qiskit_prob[index] - value) for index, value in expected.items())
        passed = (result["status"] == "PASS" and expected_dense <= PROBABILITY_MAX_TOLERANCE
                  and expected_qiskit <= PROBABILITY_MAX_TOLERANCE)
        cases.append({"name": name, "status": "PASS" if passed else "FAIL",
                      "seed": seed, "source": result["source"],
                      "parsed_gate_sequence": result["parsed_gate_sequence"],
                      "generated_gate_sequence": result["generated_gate_sequence"],
                      "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                      "source_sha256": result["source_sha256"],
                      "max_analytic_probability_error_sharkbyte": expected_dense,
                      "max_analytic_probability_error_qiskit": expected_qiskit,
                      "qiskit_vs_sharkbyte": result["probability_comparison"]})
    return {"status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
            "summary": {"interference_cases": len(cases)}, "cases": cases}


def validate_controlled_phase() -> dict:
    cases = []
    angle = 0.8125
    seed = MASTER_SEED + RANDOM_CIRCUIT_COUNT + 21
    for control in range(3):
        for target in range(3):
            if control == target:
                continue
            gates = [("x", control), ("x", target), ("cp", control, target, angle)]
            source = render_program(3, gates, seed)
            result = _evaluate_source(source, seed, gates, include_vectors=False)
            parsed = cli.parse_quantum(source)
            dense_state = quantum.simulate(parsed)
            _, qiskit_state = _build_qiskit(parsed, gates)
            basis = (1 << control) | (1 << target)
            expected = cmath.exp(1j * angle)
            dense_error = abs(dense_state[basis] - expected)
            qiskit_error = abs(complex(qiskit_state[basis]) - expected)
            leakage = max((abs(value) for index, value in enumerate(dense_state) if index != basis), default=0.0)
            passed = (result["status"] == "PASS" and dense_error <= AMPLITUDE_TOLERANCE
                      and qiskit_error <= AMPLITUDE_TOLERANCE and leakage <= AMPLITUDE_TOLERANCE)
            cases.append({"control": control, "target": target,
                          "status": "PASS" if passed else "FAIL",
                          "seed": seed, "source": result["source"],
                          "parsed_gate_sequence": result["parsed_gate_sequence"],
                          "generated_gate_sequence": result["generated_gate_sequence"],
                          "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                          "source_sha256": result["source_sha256"],
                          "sharkbyte_expected_phase_error": dense_error,
                          "qiskit_expected_phase_error": qiskit_error,
                          "sharkbyte_leakage_max": leakage})
    return {"status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
            "summary": {"ordered_control_target_pairs": len(cases), "angle_radians": angle},
            "cases": cases}


def validate_numerical_boundaries() -> dict:
    accepted = []
    rejected = []
    seed = MASTER_SEED + RANDOM_CIRCUIT_COUNT + 22
    for op in ("cp", "rx", "ry", "rz"):
        for angle in (0.0, 1e-15, -1e-15, ANGLE_LIMIT, -ANGLE_LIMIT):
            if op == "cp":
                gates, qubits = [("h", 0), ("h", 1), (op, 0, 1, angle)], 2
            else:
                gates, qubits = [("h", 0), (op, 0, angle)], 1
            source = render_program(qubits, gates, seed)
            try:
                result = _evaluate_source(source, seed, gates, include_vectors=False)
                accepted.append({"op": op, "angle": angle, "seed": seed,
                                 "source": result["source"],
                                 "parsed_gate_sequence": result["parsed_gate_sequence"],
                                 "generated_gate_sequence": result["generated_gate_sequence"],
                                 "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                                 "status": result["status"],
                                 "source_sha256": result["source_sha256"],
                                 "max_norm_error": result["normalization"]["max_norm_error_from_one"]})
            except Exception as exc:
                accepted.append({"op": op, "angle": angle, "status": "FAIL",
                                 "seed": seed, "source": source,
                                 "source_sha256": _sha256(source.encode("utf-8")),
                                 "error_type": type(exc).__name__, "error": str(exc)})
    just_outside = math.nextafter(ANGLE_LIMIT, math.inf)
    for op in ("cp", "rx", "ry", "rz"):
        for angle in (just_outside, -just_outside):
            source = (render_program(2, [(op, 0, 1, angle)], seed) if op == "cp"
                      else render_program(1, [(op, 0, angle)], seed))
            try:
                cli.parse_quantum(source)
                rejected.append({"op": op, "angle": angle, "seed": seed, "source": source,
                                 "source_sha256": _sha256(source.encode("utf-8")),
                                 "status": "FAIL",
                                 "reason": "out-of-range angle was accepted"})
            except ValueError as exc:
                rejected.append({"op": op, "angle": angle, "seed": seed, "source": source,
                                 "source_sha256": _sha256(source.encode("utf-8")),
                                 "status": "PASS", "error": str(exc)})
    nonfinite = []
    for op in ("cp", "rx", "ry", "rz"):
        for token in ("nan", "inf", "-inf"):
            body = f"cp {token} 0 1" if op == "cp" else f"{op} {token} 0"
            source = f"qubits {2 if op == 'cp' else 1};\nshots 1;\nseed {seed};\n{body};\nmeasure_all;\n"
            try:
                cli.parse_quantum(source)
                nonfinite.append({"op": op, "token": token, "seed": seed, "source": source,
                                  "source_sha256": _sha256(source.encode("utf-8")),
                                  "status": "FAIL"})
            except ValueError:
                nonfinite.append({"op": op, "token": token, "seed": seed, "source": source,
                                  "source_sha256": _sha256(source.encode("utf-8")),
                                  "status": "PASS"})
    passed = all(c["status"] == "PASS" for c in accepted + rejected + nonfinite)
    return {"status": "PASS" if passed else "FAIL",
            "summary": {"accepted_boundary_cases": len(accepted),
                        "rejected_out_of_range_cases": len(rejected),
                        "rejected_nonfinite_cases": len(nonfinite),
                        "angle_limit_radians": ANGLE_LIMIT},
            "accepted": accepted, "rejected_out_of_range": rejected,
            "rejected_nonfinite": nonfinite}


def validate_bit_ordering() -> dict:
    cases = []
    seed = MASTER_SEED + RANDOM_CIRCUIT_COUNT + 23
    for qubit in range(4):
        source = render_program(4, [("x", qubit)], seed)
        gates = [("x", qubit)]
        result = _evaluate_source(source, seed, gates, include_vectors=False)
        parsed = cli.parse_quantum(source)
        dense = quantum.simulate(parsed)
        _, qiskit_state = _build_qiskit(parsed, gates)
        display_probabilities = quantum.evaluate(parsed)["probabilities"]
        expected_index = 1 << qubit
        dense_index = max(range(len(dense)), key=lambda index: abs(dense[index]))
        qiskit_index = max(range(len(qiskit_state)), key=lambda index: abs(qiskit_state[index]))
        label = sparse_backend.format_basis(expected_index, 4)
        expected_label = format(expected_index, "04b")
        passed = (result["status"] == "PASS" and dense_index == expected_index
                  and qiskit_index == expected_index and label == expected_label
                  and max(display_probabilities, key=display_probabilities.get) == expected_label
                  and abs(display_probabilities[expected_label] - 1.0) <= PROBABILITY_MAX_TOLERANCE)
        cases.append({"x_qubit": qubit, "expected_basis_index": expected_index,
                      "expected_display_label": expected_label,
                      "sharkbyte_reported_display_label": max(display_probabilities, key=display_probabilities.get),
                      "seed": seed, "source": result["source"],
                      "parsed_gate_sequence": result["parsed_gate_sequence"],
                      "generated_gate_sequence": result["generated_gate_sequence"],
                      "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                      "status": "PASS" if passed else "FAIL",
                      "source_sha256": result["source_sha256"]})
    # q2 controls q0; basis index 5 distinguishes integer index from label order.
    source = render_program(3, [("x", 2), ("cx", 2, 0)], seed)
    gates = [("x", 2), ("cx", 2, 0)]
    result = _evaluate_source(source, seed, gates, include_vectors=False)
    parsed = cli.parse_quantum(source)
    dense = quantum.simulate(parsed)
    _, qiskit_state = _build_qiskit(parsed, gates)
    display_probabilities = quantum.evaluate(parsed)["probabilities"]
    cases.append({"control": 2, "target": 0, "expected_basis_index": 5,
                  "expected_display_label": "101",
                  "sharkbyte_reported_display_label": max(display_probabilities, key=display_probabilities.get),
                  "seed": seed, "source": result["source"],
                  "parsed_gate_sequence": result["parsed_gate_sequence"],
                  "generated_gate_sequence": result["generated_gate_sequence"],
                  "qiskit_gate_sequence": result["qiskit_gate_sequence"],
                  "status": "PASS" if result["status"] == "PASS"
                  and max(range(len(dense)), key=lambda i: abs(dense[i])) == 5
                  and max(range(len(qiskit_state)), key=lambda i: abs(qiskit_state[i])) == 5
                  and max(display_probabilities, key=display_probabilities.get) == "101"
                  and abs(display_probabilities["101"] - 1.0) <= PROBABILITY_MAX_TOLERANCE
                  else "FAIL", "source_sha256": result["source_sha256"]})
    return {"status": "PASS" if all(c["status"] == "PASS" for c in cases) else "FAIL",
            "summary": {"bit_order_cases": len(cases),
                        "convention": "q0 least-significant; displayed strings MSB-left"},
            "cases": cases}


def validate_global_phase_alignment() -> dict:
    expected = [1.0 / math.sqrt(2.0), 1j / math.sqrt(2.0), 0j, 0j]
    phase = cmath.exp(0.731j)
    actual = [value * phase for value in expected]
    metrics = _state_metrics(expected, actual)
    raw_max = max(abs(a - b) for a, b in zip(expected, actual))
    passed = (raw_max > 1e-3
              and metrics["max_complex_amplitude_error_global_phase_aligned"] <= 1e-14)
    return {"status": "PASS" if passed else "FAIL",
            "summary": {"synthetic_phase_radians": 0.731,
                        "raw_max_amplitude_difference": raw_max,
                        "aligned_max_amplitude_error": metrics["max_complex_amplitude_error_global_phase_aligned"],
                        "overlap_magnitude": metrics["overlap_magnitude"],
                        "expected_amplitudes_real_imag": [[z.real, z.imag] for z in expected],
                        "phase_shifted_amplitudes_real_imag": [[z.real, z.imag] for z in actual]}}


def _versions() -> dict:
    names = ("qiskit", "numpy", "scipy", "rustworkx", "sharkbyte-standalone-alpha")
    result = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "NOT_INSTALLED"
    distributions = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            distributions[name] = distribution.version
    result["all_distributions"] = dict(
        sorted(distributions.items(), key=lambda item: item[0].casefold())
    )
    return result


def _source_hashes() -> dict:
    paths = [
        ROOT / "sharkbyte_alpha" / "quantum.py",
        ROOT / "sharkbyte_alpha" / "cli.py",
        BENCHMARK_DIR / "sparse_backend.py",
        BENCHMARK_DIR / "frontier30.py",
        BENCHMARK_DIR / "quantum_frontend.py",
        ROOT / "validation" / "independent_qiskit" / "suite.py",
        ROOT / "validation" / "independent_qiskit" / "test_suite.py",
        ROOT / "tools" / "run_independent_quantum_validation.py",
        ROOT / "requirements-independent-quantum.txt",
        ROOT / ".github" / "workflows" / "independent-quantum-validation.yml",
    ]
    return {str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path.read_bytes())
            for path in paths}


def _revision() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              check=True, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None


def run_validations() -> dict:
    started = time.monotonic()
    sections = {}
    failures = []
    for name, function in (
        ("randomized_live_statevector", validate_randomized),
        ("gate_inverses", validate_gate_inverses),
        ("interference", validate_interference),
        ("controlled_phase", validate_controlled_phase),
        ("numerical_boundaries", validate_numerical_boundaries),
        ("bit_ordering", validate_bit_ordering),
        ("global_phase_alignment", validate_global_phase_alignment),
    ):
        try:
            section = function()
        except Exception as exc:
            section = {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}
        sections[name] = section
        if section.get("status") != "PASS":
            failures.append(name)
    random_section = sections.get("randomized_live_statevector", {})
    random_cases = random_section.get("cases", [])
    sparse_pass_count = sum(bool(case.get("checks", {}).get("sparse_dense_amplitudes")
                                 and case.get("checks", {}).get("sparse_dense_probabilities"))
                            for case in random_cases)
    sparse_summary = {
        "status": "PASS" if random_cases and sparse_pass_count == len(random_cases) else "FAIL",
        "circuits_compared": len(random_cases),
        "passed": sparse_pass_count,
        "failed": len(random_cases) - sparse_pass_count,
        "max_amplitude_error": max((case.get("sparse_dense_comparison", {}).get(
            "max_complex_amplitude_error_global_phase_aligned", 0.0) for case in random_cases), default=0.0),
        "max_probability_error": max((case.get("sparse_dense_comparison", {}).get(
            "max_probability_error", 0.0) for case in random_cases), default=0.0),
    }
    sections["sparse_dense_agreement"] = sparse_summary
    if sparse_summary["status"] != "PASS":
        failures.append("sparse_dense_agreement")
    try:
        qiskit_version = importlib.metadata.version("qiskit")
    except importlib.metadata.PackageNotFoundError:
        qiskit_version = "NOT_INSTALLED"
    return {
        "schema": 1,
        "suite": "SharkByte Independent Quantum Validation",
        "status": "FAIL" if failures else "PASS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "revision": _revision(),
        "host": {"system": platform.system(), "release": platform.release(),
                 "architecture": platform.machine(), "python": platform.python_version(),
                 "implementation": platform.python_implementation()},
        "packages": _versions(),
        "qiskit_execution": {"reference": "qiskit.quantum_info.Statevector.from_instruction",
                             "version": qiskit_version, "hardware_used": False},
        "methodology": {
            "master_seed": MASTER_SEED,
            "exact_randomized_seeds": [MASTER_SEED + i for i in range(RANDOM_CIRCUIT_COUNT)],
            "randomized_circuits_requested": RANDOM_CIRCUIT_COUNT,
            "supported_gates": list(SUPPORTED_GATES),
            "qubit_range": [1, 6],
            "endianness": "q0 least-significant basis-index bit; displayed labels MSB-left",
            "amplitude_tolerance": AMPLITUDE_TOLERANCE,
            "probability_max_tolerance": PROBABILITY_MAX_TOLERANCE,
            "probability_l1_tolerance": PROBABILITY_L1_TOLERANCE,
            "normalization_tolerance": NORMALIZATION_TOLERANCE,
            "sparse_amplitude_tolerance": SPARSE_AMPLITUDE_TOLERANCE,
            "sparse_probability_tolerance": SPARSE_PROBABILITY_TOLERANCE,
        },
        "source_hashes": _source_hashes(),
        "sections": sections,
        "summary": {"section_count": len(sections), "failures": failures,
                    "duration_seconds": time.monotonic() - started,
                    "randomized_circuits": random_section.get("summary", {}).get("circuits", 0),
                    "randomized_passed": random_section.get("summary", {}).get("passed", 0),
                    "randomized_failed": random_section.get("summary", {}).get("failed", 0)},
    }
