"""Verify a compact receipt created by the Studio 16,777,216-state run."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))

from sharkbyte_alpha.cli import canonical, verify as verify_integrity
from support_scaling import build_circuit

STATES = 1 << 24


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_studio_scaling_record(record):
    """Verify source binding, gate identity, numerical claims, and references."""
    integrity = verify_integrity(record)
    if record.get("mode") != "scaling_16m":
        raise ValueError("receipt is not a Studio 16,777,216-state run")
    source = record.get("source")
    expected_source = (ROOT / "examples" / "frontier_sparse_40_131072.sb").read_text(encoding="utf-8")
    if source != expected_source:
        raise ValueError("receipt source does not match the checked-in scaling source")

    result = record.get("result")
    if not isinstance(result, dict) or result.get("status") != "PASS":
        raise ValueError("benchmark result is not PASS")
    if (result.get("qubits"), result.get("gates"), result.get("final_active_states"),
            result.get("peak_active_states")) != (40, 56, STATES, STATES):
        raise ValueError("register, gate, or active-state count does not match the experiment")
    circuit, source_sha256, added_gates, _ = build_circuit(STATES)
    if result.get("source_sha256") != source_sha256:
        raise ValueError("benchmark source digest differs from the checked-in source")
    if result.get("added_gates") != [list(gate) for gate in added_gates]:
        raise ValueError("benchmark extension gates differ from the canonical circuit")

    identity = result.get("circuit_identity")
    expected_identity = {
        "name": circuit.name, "qubits": circuit.qubits,
        "gate_count": len(circuit.gates), "gates": [list(gate) for gate in circuit.gates],
        "base_source_sha256": source_sha256,
    }
    if not isinstance(identity, dict):
        raise ValueError("complete executed-circuit identity is absent")
    if {key: identity.get(key) for key in expected_identity} != expected_identity:
        raise ValueError("executed-circuit identity differs from the canonical gates")
    if identity.get("sha256") != _digest(canonical(expected_identity)):
        raise ValueError("executed-circuit digest mismatch")

    checks = result.get("verification")
    if not isinstance(checks, dict) or checks.get("status") != "PASS":
        raise ValueError("numerical verification status is not PASS")
    if not all(checks.get(key) is True for key in (
            "populated_state_count_pass", "peak_state_count_pass",
            "normalization_pass", "uniform_probability_pass")):
        raise ValueError("one or more numerical verification checks are false")
    if abs(float(result.get("probability_sum", float("nan"))) - 1.0) > 1e-12:
        raise ValueError("probability normalization is outside tolerance")
    if float(result.get("max_uniform_probability_error", float("inf"))) > (1 / STATES) * 1e-12:
        raise ValueError("uniform-probability error exceeds tolerance")
    result_hash = result.get("result_sha256")
    result_body = {key: value for key, value in result.items() if key != "result_sha256"}
    if result_hash != _digest(canonical(result_body)):
        raise ValueError("benchmark-result digest mismatch")

    studio = result.get("studio_execution")
    if not isinstance(studio, dict):
        raise ValueError("Studio execution measurements are absent")
    if not isinstance(studio.get("source_revision"), str) or len(studio["source_revision"]) != 40:
        raise ValueError("source revision is missing or malformed")
    memory = studio.get("process_peak_memory_bytes")
    limits = studio.get("resource_limits")
    if type(memory) is not int or memory <= 0 or not isinstance(limits, dict):
        raise ValueError("measured worker memory or configured limits are absent")
    if memory > limits.get("process_memory_limit_bytes", 0):
        raise ValueError("measured process memory exceeds the configured hard limit")
    if limits.get("preflight_available_memory_bytes", 0) < limits.get("minimum_available_memory_bytes", 1):
        raise ValueError("run did not satisfy the memory preflight")
    if not isinstance(studio.get("worker_wall_seconds"), (int, float)) or studio["worker_wall_seconds"] <= 0:
        raise ValueError("worker wall time is missing")

    refs = checks.get("independent_reference_receipts")
    expected_ref_paths = {
        "benchmarks/sb_quantum_benchmark/scaling-16777216-cirq.json",
        "evidence/windows-arm64-cirq/cirq-16777216.json",
    }
    if not isinstance(refs, list) or {ref.get("receipt_path") for ref in refs} != expected_ref_paths:
        raise ValueError("both archived Cirq full-statevector receipts are not referenced")
    for ref in refs:
        path = ROOT / Path(ref["receipt_path"])
        if not path.is_file() or _digest(path.read_bytes()) != ref.get("receipt_sha256"):
            raise ValueError(f"independent reference receipt hash mismatch: {ref.get('receipt_path')}")
        archived = json.loads(path.read_text(encoding="utf-8"))
        if (archived.get("status") != "PASS" or archived.get("source_sha256") != source_sha256
                or archived.get("qubits") != 40 or archived.get("gates") != 56
                or archived.get("compared_amplitudes") != STATES):
            raise ValueError(f"independent reference does not verify this circuit: {path.name}")
    return {
        "status": "STUDIO_SCALING_RECEIPT_VERIFIED",
        "integrity": integrity["status"],
        "qubits": 40, "gates": 56, "active_states": STATES,
        "circuit_sha256": identity["sha256"],
        "process_peak_memory_bytes": memory,
        "note": "Hashes establish integrity, not authorship. The archived Cirq records are separate historical runs of the identical source and gate sequence.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    record = json.loads(args.receipt.read_text(encoding="utf-8"))
    print(json.dumps(verify_studio_scaling_record(record), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"studio receipt verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
