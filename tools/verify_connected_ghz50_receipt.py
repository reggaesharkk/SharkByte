"""Verify integrity and provenance fields of a 50-qubit materialization receipt.

This verifier does not recreate the temporary multi-gigabyte arrays. It checks
the receipt digest, the recorded Git revision's source/code/notebook bytes, and
the internal structural claims. Reproducing the full-array result requires
rerunning the Colab notebook.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def git_bytes(commit: str, relative_path: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{commit}:{relative_path}"], cwd=ROOT
    )


def verify(path: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    claimed = report.get("receipt_sha256")
    unsigned = {key: value for key, value in report.items()
                if key != "receipt_sha256"}
    if claimed != canonical_hash(unsigned):
        raise ValueError("receipt SHA-256 mismatch")
    if report.get("format") != "sharkbyte-connected-ghz50-disk-materialization-v1":
        raise ValueError("unrecognized receipt format")
    commit = report.get("source_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("missing or invalid source commit")
    source_path = report["source_path"]
    source_raw = git_bytes(commit, source_path)
    if hashlib.sha256(source_raw).hexdigest() != report.get("source_sha256"):
        raise ValueError("recorded source SHA-256 does not match the commit")
    for relative_path, expected in report.get("code_sha256", {}).items():
        if hashlib.sha256(git_bytes(commit, relative_path)).hexdigest() != expected:
            raise ValueError(f"source-code hash mismatch: {relative_path}")
    notebook_sha = report.get("notebook_sha256")
    if notebook_sha:
        notebook_raw = git_bytes(commit, "notebooks/SharkByte-Colab-Connected-50Q-2B.ipynb")
        if hashlib.sha256(notebook_raw).hexdigest() != notebook_sha:
            raise ValueError("notebook SHA-256 does not match the source commit")
    circuit = report.get("circuit_identity", {})
    qubits = circuit.get("qubits")
    gates = circuit.get("gate_count")
    expanded = circuit.get("expanded_local_hadamards")
    states = report.get("target_active_states")
    if (qubits != 50 or not isinstance(expanded, int)
            or not 0 <= expanded <= 31 or gates != 50 + expanded
            or states != (1 << (expanded + 1))
            or report.get("packed_array_bytes") != states * 24):
        raise ValueError("circuit identity or packed-array size is inconsistent")
    if report.get("status") == "PASS":
        check = report.get("full_array_check", {})
        if (check.get("status") != "PASS"
                or check.get("basis_entries_compared") != states
                or check.get("complex_amplitudes_compared") != states
                or check.get("probability_sum") is None
                or abs(check["probability_sum"] - 1.0) > 2e-12
                or check.get("temporary_arrays_retained") is not False
                or report.get("cirq_reference", {}).get("status") != "PASS"
                or report.get("entanglement_witness", {}).get("status") != "PASS"):
            raise ValueError("PASS receipt is missing a required recorded check")
        for key in ("basis_array_sha256", "amplitude_array_sha256"):
            value = check.get(key, "")
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"invalid {key}")
    elif report.get("status") not in {"REFUSED", "RESOURCE_STOP", "FAIL"}:
        raise ValueError("unknown receipt status")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.receipt.resolve())
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"RECEIPT_INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"RECEIPT_INTEGRITY_VERIFIED: status={report['status']} "
          f"qubits=50 states={report['target_active_states']:,} "
          f"commit={report['source_commit']}")
    if report["status"] == "PASS":
        print("Recorded full-array and Cirq checks are internally consistent. "
              "This verifies receipt integrity, not authorship or a fresh rerun.")
        print("The large temporary arrays were deleted; reproducing their full "
              "contents requires rerunning the notebook.")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
