"""Independent integrity, analytic-reference and exact-certificate replay for frontier receipts."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

from sparse_backend import Circuit
from benchmarks.sb_quantum_benchmark.certified_support import verify as verify_support_certificate


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                            allow_nan=False).encode("utf-8")).hexdigest()


def _state_hash(state):
    digest = hashlib.sha256()
    for basis in sorted(state):
        amp = state[basis]
        digest.update(f"{basis}:{amp.real.hex()}:{amp.imag.hex()}\n".encode("ascii"))
    return digest.hexdigest()


def _read_state(rows):
    state = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError("malformed basis/amplitude row")
        basis, real_hex, imag_hex = row
        if type(basis) is not int or basis < 0 or basis in state:
            raise ValueError("invalid or duplicate basis index")
        real, imag = float.fromhex(real_hex), float.fromhex(imag_hex)
        if not math.isfinite(real) or not math.isfinite(imag) or real.hex() != real_hex or imag.hex() != imag_hex:
            raise ValueError("noncanonical or nonfinite amplitude")
        state[basis] = complex(real, imag)
    return state


def _source_hashes():
    names = (
        "benchmarks/sb_quantum_benchmark/sparse_backend.py",
        "benchmarks/sb_quantum_benchmark/frontier30.py",
        "benchmarks/sb_quantum_benchmark/bounded_support.py",
        "benchmarks/sb_quantum_benchmark/certified_support.py",
        "tools/high_support/dense_statevector.py",
        "tools/high_support/adaptive_statevector.py",
        "tools/high_support/frontier_scaling.py",
        "tools/high_support/verify_frontier_scaling.py",
    )
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in names if (ROOT / name).is_file()}


def _reduce_independently(gates):
    stack, pairs = [], []
    for index, raw in enumerate(gates):
        gate = tuple(raw)
        if stack:
            left_index, previous = stack[-1]
            op = gate[0]
            inverse = (previous == gate if op in ("h", "x", "z", "cx") else
                       previous[:-1] == gate[:-1] and previous[-1] == -gate[-1]
                       if op in ("cp", "rx", "ry", "rz") else False)
            if inverse:
                stack.pop()
                pairs.append([left_index, index])
                continue
        stack.append((index, gate))
    return [list(gate) for _, gate in stack], pairs


def _expected_gates(family, qubits, seed):
    if family == "basis-walk":
        rng = random.Random(seed + qubits * 1009)
        gates = []
        for _ in range(64):
            op = rng.choice(("x", "z", "cx"))
            gates.append([op, *rng.sample(range(qubits), 2)] if op == "cx"
                         else [op, rng.randrange(qubits)])
        return gates
    if family == "connected-ghz":
        return [["h", 0]] + [["cx", q - 1, q] for q in range(1, qubits)]
    if family == "growing-support":
        return [["h", q] for q in range(qubits)]
    if family == "interference":
        return [["h", 0], ["z", 0], ["h", 0]] + [["cx", 0, q] for q in range(1, qubits)]
    if family == "uncomputation":
        return ([["h", q] for q in range(qubits)] +
                [["cp", 0, qubits - 1, 0.371], ["cp", 0, qubits - 1, -0.371]] +
                [["h", q] for q in reversed(range(qubits))])
    if family == "dense-no-benefit":
        return [["h", q] for q in range(qubits)] + [["z", q] for q in range(qubits)]
    raise ValueError("unknown workload family")


def _expected_sparse_digest(family, qubits, gates):
    inv = 1.0 / math.sqrt(2.0)
    if family == "basis-walk":
        basis, amp = 0, 1.0 + 0.0j
        for gate in gates:
            if gate[0] == "x":
                basis ^= 1 << gate[1]
            elif gate[0] == "cx" and basis & (1 << gate[1]):
                basis ^= 1 << gate[2]
            elif gate[0] == "z" and basis & (1 << gate[1]):
                amp = -amp
        return _state_hash({basis: amp})
    if family == "connected-ghz":
        return _state_hash({0: complex(inv, 0.0), (1 << qubits)-1: complex(inv, 0.0)})
    if family == "interference":
        low, high = inv, -inv
        low, high = (low + high) * inv, (low - high) * inv
        return _state_hash({(1 << qubits)-1: complex(high, 0.0)})
    if family == "growing-support":
        amp = 1.0
        for _ in range(qubits):
            amp *= inv
        digest = hashlib.sha256()
        token = f":{amp.hex()}:0x0.0p+0\n".encode("ascii")
        for basis in range(1 << qubits):
            digest.update(f"{basis}".encode("ascii"))
            digest.update(token)
        return digest.hexdigest()
    if family == "dense-no-benefit":
        amp = 1.0
        for _ in range(qubits):
            amp *= inv
        digest = hashlib.sha256()
        for basis in range(1 << qubits):
            value = complex(amp, 0.0)
            if basis.bit_count() % 2:
                value = -value
            digest.update(f"{basis}:{value.real.hex()}:{value.imag.hex()}\n".encode("ascii"))
        return digest.hexdigest()
    return None


def _verify_compaction(payload):
    gates = tuple(tuple(gate) for gate in payload["gates"])
    initial = _read_state(payload["initial_state"])
    output = _read_state(payload["output_state"])
    circuit = Circuit(payload["qubits"], gates, payload["family"])
    qubits = payload["qubits"]
    if qubits != 9:
        raise ValueError("compaction control width mismatch")
    if payload["family"] == "compaction-helpful":
        tiny = 1e-10
        expected_initial = {0: complex(math.sqrt(1.0 - 255*tiny*tiny), 0.0)}
        expected_initial.update({basis: complex(tiny, 0.0) for basis in range(1, 256)})
        expected_gates = [["x", i % qubits] for i in range(96)]
    elif payload["family"] == "compaction-no-benefit":
        expected_initial = {basis: complex(1/16, 0.0) for basis in range(256)}
        expected_gates = [["x", i % qubits] if i % 3 == 0 else
                          (["z", i % qubits] if i % 3 == 1 else
                           ["cx", i % qubits, (i+1) % qubits]) for i in range(96)]
    else:
        raise ValueError("unknown compaction workload")
    if [list(g) for g in gates] != expected_gates or initial != expected_initial:
        raise ValueError("compaction workload differs from independently defined control")
    cert = payload["certificate"]
    if _canonical_hash(cert) != payload["certificate_sha256"]:
        raise ValueError("compaction certificate digest mismatch")
    certificate_size = len(json.dumps(cert, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if certificate_size != payload["certificate_bytes"]:
        raise ValueError("compaction certificate byte count mismatch")
    replay = verify_support_certificate(circuit, initial, output, cert, payload["budget"])
    if replay.get("status") != "PASS" or payload["replay"].get("status") != "PASS":
        raise ValueError("exact Fraction replay failed")
    if replay.get("exact_squared_error") != payload["replay"].get("exact_squared_error"):
        raise ValueError("recorded and independently replayed squared error differ")
    if _state_hash(output) != payload["compacted_state_sha256"]:
        raise ValueError("compacted output state digest mismatch")
    if len(output) != payload["compacted_support"]:
        raise ValueError("compacted support count mismatch")
    if not Fraction(payload["deletion_l2_bound"]) <= Fraction(payload["budget"]):
        raise ValueError("deletion bound exceeds requested budget")
    if payload["family"] == "compaction-helpful" and payload["compacted_support"] >= payload["baseline_support"]:
        raise ValueError("helpful case did not reduce support")
    if payload["family"] == "compaction-no-benefit" and payload["compacted_support"] != payload["baseline_support"]:
        raise ValueError("no-benefit control unexpectedly changed support")
    return {"status": "PASS", "exact_fraction_replay": replay}


def verify_receipt(path, *, required_backends=()):
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt.get("schema") != "sharkbyte-frontier-scaling-v1":
        raise ValueError("unknown receipt schema")
    recorded = receipt.get("record_sha256")
    unsigned = dict(receipt)
    unsigned.pop("record_sha256", None)
    if recorded != _canonical_hash(unsigned):
        raise ValueError("receipt hash mismatch")
    if receipt.get("source_sha256") != _source_hashes():
        raise ValueError("source-bound module hash mismatch")
    memory_limit = receipt["configuration"]["worker_memory_limit_bytes"]
    ref_qubits = receipt["configuration"]["full_reference_qubits"]
    required_backends = tuple(required_backends)
    checked_cases = 0
    unsupported_cases = 0
    for row in receipt["cases"]:
        status = row.get("status")
        plan = row["resource_plan"]
        if status == "UNSUPPORTED":
            unsupported_cases += 1
            if row.get("reason", "").startswith(("pre-run memory plan", "pre-run compaction plan")):
                if plan["combined_planning_bytes"] <= memory_limit:
                    raise ValueError("case refused despite fitting its configured memory plan")
            continue
        if status != "PASS":
            raise ValueError(f"case did not pass: {row.get('family')}/{row.get('qubits')}")
        payload = row["payload"]
        family, qubits = row["family"], row["qubits"]
        if family.startswith("compaction-"):
            if payload.get("family") != family or payload.get("qubits") != qubits:
                raise ValueError("compaction workload label differs from worker payload")
            _verify_compaction(payload)
            checked_cases += 1
            continue
        if payload.get("family") != family or payload.get("qubits") != qubits:
            raise ValueError("case label differs from worker payload")
        repetitions = payload.get("repetitions")
        if len(repetitions) != receipt["configuration"]["repeats"]:
            raise ValueError("repetition count mismatch")
        gates = repetitions[0]["gates"]
        if gates != _expected_gates(family, qubits, payload["seed"]):
            raise ValueError("circuit source differs from independent seeded family construction")
        circuit_digest = _canonical_hash({"qubits": qubits, "gates": gates})
        expected_digest = _expected_sparse_digest(family, qubits, gates)
        for repetition in repetitions:
            if (repetition.get("primary_representation") != "sparse basis-to-amplitude dictionary"
                    or repetition.get("full_statevector_materialized_by_primary_engine") is not False
                    or repetition.get("analytically_generated_state_entries") != 0
                    or repetition.get("state_dimension") != 1 << qubits):
                raise ValueError("state storage and analytic-reference labels are inconsistent")
            if repetition["gates"] != gates or repetition["circuit_sha256"] != circuit_digest:
                raise ValueError("generated circuit changed between repetitions or digest mismatch")
            simplified, pairs = _reduce_independently(gates)
            if repetition["simplified_gates"] != simplified:
                raise ValueError("simplified circuit differs from independent stack reduction")
            if repetition["cancellation_pairs_zero_based"] != pairs:
                raise ValueError("inverse cancellation index certificate mismatch")
            if repetition["source_gate_count"] != len(gates) or repetition["simplified_gate_count"] != len(simplified):
                raise ValueError("gate count mismatch")
            if expected_digest is not None and repetition["state_sha256"] != expected_digest:
                raise ValueError("statevector digest differs from the independent analytic reference")
            sparse_entries = repetition.get("sparse_state_entries")
            if sparse_entries is not None:
                observed = _read_state(sparse_entries)
                if len(observed) != repetition["final_support"] or _state_hash(observed) != repetition["state_sha256"]:
                    raise ValueError("stored sparse state entries do not match their support count and digest")
                norm = math.fsum(abs(value)**2 for value in observed.values())
                if abs(norm-repetition["probability_sum"]) > 1e-15:
                    raise ValueError("sparse-state norm differs from the recorded probability sum")
                if family == "uncomputation":
                    ideal_error = math.sqrt(math.fsum(abs(value-(1.0 if basis == 0 else 0.0))**2
                                                       for basis, value in observed.items())
                                             + (1.0 if 0 not in observed else 0.0))
                    if abs(ideal_error-repetition["analytic_check"]["max_or_l2_error"]) > 1e-15:
                        raise ValueError("uncomputation ideal-state error differs from stored amplitudes")
            elif repetition["final_support"] <= 4096:
                raise ValueError("small sparse output omitted its independently checkable amplitude table")
            if repetition["optimized"] is not None:
                if family == "uncomputation":
                    expected_optimized = _state_hash({0: 1.0+0.0j})
                else:
                    expected_optimized = _expected_sparse_digest(family, qubits, simplified)
                if (expected_optimized is not None
                        and repetition["optimized"]["state_sha256"] != expected_optimized):
                    raise ValueError("simplified execution differs from its independent analytic reference")
            for backend in required_backends:
                if qubits <= ref_qubits:
                    reference = repetition["independent_references"].get(backend)
                    if reference is None or reference.get("status") != "PASS":
                        raise ValueError(f"required {backend} full-vector comparison missing or failed")
            for backend, reference in repetition["independent_references"].items():
                if reference["status"] == "PASS" and reference.get("max_complex_amplitude_error", math.inf) > 2e-10:
                    raise ValueError(f"{backend} statevector comparison exceeds tolerance")
                if reference["status"] == "PASS" and reference.get("reference_type") != "complete dense complex128 statevector":
                    raise ValueError(f"{backend} comparison is not identified as a full statevector")
        if len({rep["state_sha256"] for rep in repetitions}) != 1:
            raise ValueError("repeated runs are not bitwise deterministic")
        checked_cases += 1
    return {"status": "PASS", "checked_cases": checked_cases,
            "resource_refusals": unsupported_cases,
            "required_backends": list(required_backends),
            "record_sha256": recorded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--require-backends", default="",
                        help="comma-separated backends that must pass every eligible full-vector comparison")
    args = parser.parse_args(argv)
    try:
        report = verify_receipt(args.receipt,
                                required_backends=tuple(filter(None, args.require_backends.split(",")))
                                )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError,
            ZeroDivisionError, OverflowError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
