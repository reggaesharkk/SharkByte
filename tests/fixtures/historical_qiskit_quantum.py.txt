"""SharkByte Quantum Lab Phase 1: bounded classical quantum simulator.
Standalone experimental backend; not integrated into SharkByte 8093.
Standard Python library only.
"""
import argparse
import hashlib
import json
import math
import re
import pathlib
import random
import uuid
from datetime import datetime, timezone

MAX_QUBITS = 6
MAX_GATES = 256
MAX_SHOTS = 100000
INV_SQRT2 = 1.0 / math.sqrt(2.0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse(source):
    if len(source.encode("utf-8")) > 65536:
        raise ValueError("Source exceeds 65536 bytes")

    n = None
    gates = []
    shots = 1024
    seed = 20261109
    measured = False

    for line_number, line in enumerate(source.splitlines(), 1):
        clean = line.split("//", 1)[0]

        for statement in clean.split(";"):
            statement = statement.strip()
            if not statement:
                continue

            parts = statement.split()
            op = parts[0].lower()
            args = parts[1:]

            try:
                if op == "qubits":
                    if n is not None or len(args) != 1:
                        raise ValueError("One qubit declaration required")
                    n = int(args[0])
                    if not 1 <= n <= MAX_QUBITS:
                        raise ValueError("Qubit limit exceeded")

                elif op == "shots":
                    if len(args) != 1:
                        raise ValueError("shots requires one integer")
                    shots = int(args[0])
                    if not 1 <= shots <= MAX_SHOTS:
                        raise ValueError("Shot limit exceeded")

                elif op == "seed":
                    if len(args) != 1:
                        raise ValueError("seed requires one integer")
                    seed = int(args[0])
                    if not 0 <= seed < 2**64:
                        raise ValueError("Invalid seed")

                elif op == "measure_all":
                    if n is None or args or measured:
                        raise ValueError("Invalid measurement")
                    measured = True

                elif op == "cp":
                    if n is None or measured:
                        raise ValueError("Gate outside quantum circuit")
                    if len(args) != 3:
                        raise ValueError("cp requires angle control target")
                    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", args[0]):
                        raise ValueError("Invalid CP decimal angle")
                    angle = float(args[0])
                    if not math.isfinite(angle) or abs(angle) > 4 * math.pi:
                        raise ValueError("CP angle outside bounded range")
                    if not all(re.fullmatch(r"[0-9]+", v) for v in args[1:]):
                        raise ValueError("Invalid CP qubit indices")
                    control, target = (int(v) for v in args[1:])
                    if control >= n or target >= n or control == target:
                        raise ValueError("Invalid CP control or target")
                    gates.append(("cp", (angle, control, target)))
                    if len(gates) > MAX_GATES:
                        raise ValueError("Gate limit exceeded")

                elif op in ("h", "x", "z", "cx"):
                    if n is None or measured:
                        raise ValueError("Gate outside quantum circuit")

                    arity = 2 if op == "cx" else 1
                    if len(args) != arity:
                        raise ValueError("Wrong gate argument count")

                    indices = tuple(int(v) for v in args)

                    if any(q < 0 or q >= n for q in indices):
                        raise ValueError("Qubit index out of range")

                    if len(set(indices)) != len(indices):
                        raise ValueError("Control and target must differ")

                    gates.append((op, indices))

                    if len(gates) > MAX_GATES:
                        raise ValueError("Gate limit exceeded")

                else:
                    raise ValueError("Unsupported operation: " + op)

            except (ValueError, OverflowError) as exc:
                raise ValueError(
                    "Line " + str(line_number) + ": " + str(exc)
                ) from exc

    if n is None or not measured:
        raise ValueError("Circuit requires qubits and measure_all")

    return {
        "n": n,
        "gates": gates,
        "shots": shots,
        "seed": seed,
    }


def simulate(circuit):
    n = circuit["n"]
    size = 1 << n
    state = [0j] * size
    state[0] = 1 + 0j

    for op, indices in circuit["gates"]:
        if op == "cp":
            angle, control, target = indices
            both = (1 << control) | (1 << target)
            phase = complex(math.cos(angle), math.sin(angle))
            for i in range(size):
                if (i & both) == both:
                    state[i] *= phase
            continue
        q = indices[0]
        mask = 1 << q

        if op == "h":
            for i in range(size):
                if i & mask:
                    continue
                j = i | mask
                a, b = state[i], state[j]
                state[i] = (a + b) * INV_SQRT2
                state[j] = (a - b) * INV_SQRT2

        elif op == "x":
            for i in range(size):
                if i & mask:
                    continue
                j = i | mask
                state[i], state[j] = state[j], state[i]

        elif op == "z":
            for i in range(size):
                if i & mask:
                    state[i] = -state[i]

        elif op == "cx":
            target_mask = 1 << indices[1]
            for i in range(size):
                if (i & mask) and not (i & target_mask):
                    j = i | target_mask
                    state[i], state[j] = state[j], state[i]

    return state


def independent_matrix_reference(circuit):
    """Separate out-of-place linear transformation implementation."""
    size = 1 << circuit["n"]
    state = [0j] * size
    state[0] = 1 + 0j

    for op, indices in circuit["gates"]:
        updated = [0j] * size
        if op == "cp":
            angle, control, target = indices
            both = (1 << control) | (1 << target)
            phase = complex(math.cos(angle), math.sin(angle))
            for i, amplitude in enumerate(state):
                updated[i] = amplitude * phase if (i & both) == both else amplitude
            state = updated
            continue
        mask = 1 << indices[0]

        for i, amplitude in enumerate(state):
            if op == "h":
                low = i & ~mask
                high = i | mask
                updated[low] += amplitude * INV_SQRT2
                sign = -1 if i & mask else 1
                updated[high] += amplitude * INV_SQRT2 * sign

            elif op == "x":
                updated[i ^ mask] += amplitude

            elif op == "z":
                sign = -1 if i & mask else 1
                updated[i] += amplitude * sign

            elif op == "cx":
                control_set = bool(i & mask)
                target_mask = 1 << indices[1]
                destination = (
                    i ^ target_mask if control_set else i
                )
                updated[destination] += amplitude

        state = updated

    return state


def evaluate(circuit):
    state = simulate(circuit)
    reference = independent_matrix_reference(circuit)

    error = max(abs(a - b) for a, b in zip(state, reference))
    norm = sum(abs(a) ** 2 for a in state)

    if error > 1e-11:
        raise RuntimeError("Quantum reference mismatch")
    if abs(norm - 1.0) > 1e-10:
        raise RuntimeError("State normalization failed")

    n = circuit["n"]
    probabilities = {
        format(i, "0" + str(n) + "b"): abs(z) ** 2
        for i, z in enumerate(state)
    }

    rng = random.Random(circuit["seed"])
    histogram = {key: 0 for key in probabilities}
    labels = list(probabilities)
    cumulative = []
    running = 0.0

    for value in probabilities.values():
        running += value / norm
        cumulative.append(running)

    for _ in range(circuit["shots"]):
        value = rng.random()
        index = len(labels) - 1

        for i, threshold in enumerate(cumulative):
            if value < threshold:
                index = i
                break

        histogram[labels[index]] += 1

    return {
        "backend": "classical_statevector_simulator",
        "real_quantum_hardware_used": False,
        "qubits": n,
        "gates": len(circuit["gates"]),
        "shots": circuit["shots"],
        "seed": circuit["seed"],
        "normalization": norm,
        "reference_max_amplitude_error": error,
        "probabilities": probabilities,
        "counts": histogram,
    }


def to_qasm(circuit):
    n = circuit["n"]
    lines = [
        "OPENQASM 3.0;",
        'include "stdgates.inc";',
        "qubit[" + str(n) + "] q;",
        "bit[" + str(n) + "] c;",
    ]

    for op, indices in circuit["gates"]:
        if op == "cx":
            a, b = indices
            lines.append(f"cx q[{a}], q[{b}];")
        elif op == "cp":
            angle, control, target = indices
            lines.append(f"cp({angle:.17g}) q[{control}], q[{target}];")
        else:
            lines.append(f"{op} q[{indices[0]}];")

    for i in range(n):
        lines.append(f"c[{i}] = measure q[{i}];")

    return "\n".join(lines) + "\n"


def near(value, expected):
    return abs(value - expected) < 1e-10


def selftest():
    cases = [
        (
            "bell",
            "qubits 2; h 0; cx 0 1; measure_all;",
            {"00": 0.5, "11": 0.5},
        ),
        (
            "ghz",
            "qubits 3; h 0; cx 0 1; cx 1 2; measure_all;",
            {"000": 0.5, "111": 0.5},
        ),
        (
            "hadamard_inverse",
            "qubits 1; h 0; h 0; measure_all;",
            {"0": 1.0},
        ),
        (
            "phase_interference",
            "qubits 1; h 0; z 0; h 0; measure_all;",
            {"1": 1.0},
        ),
        (
            "x_and_control",
            "qubits 2; x 0; cx 0 1; measure_all;",
            {"11": 1.0},
        ),
    ]

    for name, source, expected in cases:
        circuit = parse(source)
        result = evaluate(circuit)

        for state, probability in result["probabilities"].items():
            if not near(probability, expected.get(state, 0)):
                raise AssertionError(name + ": probability mismatch")

        if sum(result["counts"].values()) != circuit["shots"]:
            raise AssertionError(name + ": shot count mismatch")

        if result["counts"] != evaluate(circuit)["counts"]:
            raise AssertionError(name + ": deterministic replay failed")

        if not to_qasm(circuit).startswith("OPENQASM 3.0;"):
            raise AssertionError(name + ": export failed")

        print(name.upper() + "=PASS")

    invalid_cases = [
        "qubits 7; measure_all;",
        "qubits 2; cx 0 0; measure_all;",
        "qubits 2; h 2; measure_all;",
        "qubits 2; h 0;",
        "qubits 2; measure_all; x 0;",
        "qubits 2; exec 0; measure_all;",
    ]

    for source in invalid_cases:
        try:
            parse(source)
        except ValueError:
            continue
        raise AssertionError("Invalid circuit was accepted")

    print("INVALID_INPUT_REJECTION=6/6_PASS")
    print("QUANTUM_PHASE1_TESTS=PASS")


def run_file(source_path, output_root):
    raw = source_path.read_bytes()
    if len(raw) > 65536:
        raise ValueError("Input too large")

    source = raw.decode("utf-8-sig")
    circuit = parse(source)
    result = evaluate(circuit)
    qasm = to_qasm(circuit)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    output = output_root / (
        "run_" + timestamp + "_" + uuid.uuid4().hex[:8]
    )
    output.mkdir(parents=True, exist_ok=False)

    qasm_path = output / "circuit.qasm"
    report_path = output / "result.json"
    manifest_path = output / "manifest.json"

    qasm_path.write_text(qasm, encoding="utf-8")
    report_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    files = {
        "source_sha256": digest(raw),
        "qasm_sha256": digest(qasm_path.read_bytes()),
        "result_sha256": digest(report_path.read_bytes()),
    }

    manifest_path.write_text(
        json.dumps({
            "schema": 1,
            "status": "EXPERIMENTAL_SIMULATION_VERIFIED",
            "hardware_used": False,
            "hashes": files,
        }, indent=2),
        encoding="utf-8",
    )

    print("SIMULATION=PASS")
    print("REFERENCE_AGREEMENT=PASS")
    print("PROBABILITIES=" + json.dumps(result["probabilities"]))
    print("COUNTS=" + json.dumps(result["counts"]))
    print("RESULT=" + str(report_path))
    print("QASM=" + str(qasm_path))
    print("MANIFEST=" + str(manifest_path))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selftest")

    execute = sub.add_parser("run")
    execute.add_argument("source", type=pathlib.Path)
    execute.add_argument("--out", type=pathlib.Path, required=True)

    args = parser.parse_args()

    if args.command == "selftest":
        selftest()
    else:
        run_file(args.source, args.out)


if __name__ == "__main__":
    main()