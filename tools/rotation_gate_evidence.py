"""Generate local analytical evidence for rotation gates across execution modes."""
import json
import math
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks/sb_quantum_benchmark"))

from frontier30 import load_circuit
from sparse_backend import ResourceLimitError, evolve
from sharkbyte_alpha import hybrid, quantum
from sharkbyte_alpha.cli import envelope, parse_quantum, verify


def close(observed, expected):
    if not math.isclose(observed, expected, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f"Expected {expected}, got {observed}")


def main():
    half_pi = "1.5707963267948966"
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "rotation.sb"
        for gate in ("rx", "ry", "rz"):
            for sign, expected in (("", 0.0), ("-", 1.0)):
                gates = f"{gate} {sign}{half_pi} 0; {gate} {half_pi} 0;"
                if gate == "rz":
                    gates = f"h 0; {gates} h 0;"
                source = f"quantum rotation {{ qubits 1; {gates} measure_all; }}"
                circuit = parse_quantum(source)
                result = quantum.evaluate(circuit)
                close(result["probabilities"]["0"], expected)
                receipt = envelope(source, "quantum", result)
                verify(receipt)
                qasm = quantum.to_qasm(circuit)
                if f"{gate}(" not in qasm:
                    raise ValueError("Missing rotation in OpenQASM")
                path.write_text(source.replace("qubits 1", "qubits 40"), encoding="utf-8")
                sparse, _ = load_circuit(path)
                state = evolve(sparse, support_cap=2)
                observed = abs(state.get(0, 0j)) ** 2
                close(observed, expected)
                close(sum(abs(amplitude) ** 2 for amplitude in state.values()), 1.0)
                cases.append(dict(gate=gate, angle_sign=sign or "+", expected_zero=expected,
                                  dense_receipt=receipt, openqasm=qasm,
                                  sparse_source=path.read_text(encoding="utf-8"),
                                  sparse_probability_zero=observed))
        for gate in ("rx", "ry", "rz"):
            path.write_text(f"quantum cap {{ qubits 40; {gate} .5 39; measure_all; }}",
                            encoding="utf-8")
            circuit, _ = load_circuit(path)
            try:
                state = evolve(circuit, support_cap=1)
            except ResourceLimitError as exc:
                if gate == "rz" or exc.requested_support != 2:
                    raise
                cases.append(dict(gate=gate, cap=1, requested_support=2, status="REFUSED"))
            else:
                if gate != "rz" or len(state) != 1:
                    raise ValueError("Incorrect sparse support behavior")
                cases.append(dict(gate=gate, cap=1, populated_states=1, status="PASS"))

    source = (ROOT / "examples/adaptive.sb").read_text(encoding="utf-8").replace(
        "h 0;\nh 1;\ncp theta 0 1;\nh 0;\nh 1;", "ry theta 0;"
    )
    result = hybrid.run(source)
    history = result["history"]
    if len(history) != 4 or len({row["theta"] for row in history}) < 2:
        raise ValueError("Adaptive run did not change theta")
    for row in history:
        report = row["report"]
        circuit = parse_quantum(report["quantum_source"])
        assert circuit["gates"] == [("ry", (row["theta"], 0))]
        close(report["quantum_result"]["result"]["probabilities"]["00"],
              math.cos(row["theta"] / 2) ** 2)
    receipt = envelope(source, "hybrid", result)
    verify(receipt)
    print(json.dumps(dict(status="PASS", platform=platform.system(),
                          architecture=platform.machine(), python=platform.python_version(),
                          cases=cases, adaptive_receipt=receipt), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
