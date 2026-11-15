"""Cross-check the live Qiskit receipt using independently built Cirq circuits."""
import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation.independent_qiskit import suite


def cirq_state(width, gates):
    qubits = cirq.LineQubit.range(width)
    circuit = cirq.Circuit()
    single = {"h": cirq.H, "x": cirq.X, "z": cirq.Z}
    rotations = {"rx": cirq.rx, "ry": cirq.ry, "rz": cirq.rz}
    for op, *args in gates:
        if op in single:
            operation = single[op](qubits[args[0]])
        elif op == "cx":
            operation = cirq.CNOT(qubits[args[0]], qubits[args[1]])
        elif op == "cp":
            control, target, angle = args
            operation = cirq.CZPowGate(exponent=angle / math.pi)(qubits[control], qubits[target])
        else:
            target, angle = args
            operation = rotations[op](angle)(qubits[target])
        circuit.append(operation, strategy=cirq.InsertStrategy.NEW)
    # Cirq lists the most significant qubit first. SharkByte q0 is the LSB.
    return cirq.Simulator(dtype=np.complex128).simulate(
        circuit, qubit_order=qubits[::-1]
    ).final_state_vector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qiskit_receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.qiskit_receipt.read_bytes()
    receipt = json.loads(raw)
    cases = receipt["sections"]["randomized_live_statevector"]["cases"]
    if receipt["status"] != "PASS" or len(cases) != suite.RANDOM_CIRCUIT_COUNT:
        raise ValueError("Expected a passing full Qiskit receipt")

    rows = []
    for seed, case in zip(range(suite.MASTER_SEED, suite.MASTER_SEED + len(cases)), cases):
        source, width, gates = suite.generate_circuit(seed)
        source_hash = hashlib.sha256(source.encode()).hexdigest()
        if (case["seed"], case["qubits"], case["source_sha256"]) != (seed, width, source_hash):
            raise ValueError(f"Qiskit receipt does not match canonical circuit for seed {seed}")
        actual = cirq_state(width, gates)
        errors = {}
        for engine in ("qiskit", "sharkbyte"):
            expected = [complex(real, imag) for real, imag in case[f"amplitudes_{engine}"]]
            errors[engine] = suite._state_metrics(expected, actual).get(
                "max_complex_amplitude_error_global_phase_aligned"
            )
        norm_error = abs(math.fsum(abs(complex(value)) ** 2 for value in actual) - 1)
        passed = (norm_error <= suite.NORMALIZATION_TOLERANCE and
                  all(value is not None and value <= suite.AMPLITUDE_TOLERANCE
                      for value in errors.values()))
        rows.append(dict(seed=seed, source_sha256=source_hash, basis_states=len(actual),
                         amplitude_errors=errors, normalization_error=norm_error, passed=passed))
    report = dict(status="PASS" if all(row["passed"] for row in rows) else "FAIL",
                  cirq_core=version("cirq-core"), numpy=np.__version__,
                  revision=suite._revision(),
                  qiskit_receipt_sha256=hashlib.sha256(raw).hexdigest(),
                  amplitude_tolerance=suite.AMPLITUDE_TOLERANCE, cases=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    print(report["status"], sum(row["passed"] for row in rows), "/", len(rows))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
