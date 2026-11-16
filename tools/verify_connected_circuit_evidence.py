"""Verify the connected-circuit evidence bundle and its receipt digests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evidence" / "connected-circuit-frontier" / "MANIFEST.json"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _verify_self_hash(receipt: dict, key: str, path: Path) -> None:
    claimed = receipt.get(key)
    unsigned = {name: value for name, value in receipt.items() if name != key}
    if not isinstance(claimed, str) or claimed != _sha256(_canonical(unsigned)):
        raise ValueError(f"{key} mismatch: {path}")


def verify(manifest_path: Path) -> dict:
    manifest = _read_json(manifest_path)
    _verify_self_hash(manifest, "manifest_sha256", manifest_path)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("manifest has no file records")

    checked = []
    for item in files:
        relative = item.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError(f"invalid manifest path: {relative!r}")
        path = (ROOT / relative).resolve()
        if ROOT.resolve() not in path.parents:
            raise ValueError(f"manifest path escapes repository: {relative}")
        raw = path.read_bytes()
        if len(raw) != item.get("bytes") or _sha256(raw) != item.get("sha256"):
            raise ValueError(f"byte size or SHA-256 mismatch: {relative}")
        checked.append(relative)
    required_files = {
        ".github/workflows/ci.yml",
        ".gitattributes",
        "README.md",
        "docs/connected-circuit-frontier.md",
        "tools/run_connected_quantum_validation.py",
        "tools/compare_connected_quantum_receipts.py",
        "tools/run_connected_sparse_analytic_validation.py",
        "tools/benchmark_connected_sparse.py",
        "tools/verify_connected_circuit_evidence.py",
        "tools/build_connected_circuit_manifest.py",
        "sharkbyte_alpha/vm.py",
        "evidence/connected-circuit-frontier/windows-arm64/qiskit-connected-entanglement-final.json",
        "evidence/connected-circuit-frontier/windows-arm64/qiskit-connected-entanglement-final.states.npz",
        "evidence/connected-circuit-frontier/windows-arm64/cirq-connected-entanglement-final.json",
        "evidence/connected-circuit-frontier/windows-arm64/cirq-connected-entanglement-final.states.npz",
        "evidence/connected-circuit-frontier/windows-arm64/qiskit-cirq-connected-entanglement-density-final.json",
        "evidence/connected-circuit-frontier/windows-arm64/analytic-connected-entangled-final.json",
        "evidence/connected-circuit-frontier/ubuntu-wsl2/analytic-connected-entangled-final.json",
    }
    if not required_files.issubset(set(checked)):
        raise ValueError(f"manifest omits required source or evidence files: {sorted(required_files - set(checked))}")

    evidence = ROOT / "evidence" / "connected-circuit-frontier"
    windows = evidence / "windows-arm64"
    linux = evidence / "ubuntu-wsl2"
    qiskit = _read_json(windows / "qiskit-connected-entanglement-final.json")
    cirq = _read_json(windows / "cirq-connected-entanglement-final.json")
    for receipt, path in (
        (qiskit, windows / "qiskit-connected-entanglement-final.json"),
        (cirq, windows / "cirq-connected-entanglement-final.json"),
    ):
        _verify_self_hash(receipt, "receipt_sha256", path)
        archive = windows / receipt["state_archive"]["file"]
        if _sha256(archive.read_bytes()) != receipt["state_archive"]["sha256"]:
            raise ValueError(f"state archive digest mismatch: {archive}")
        if receipt.get("status") != "PASS" or receipt.get("corpus_cases") != 24:
            raise ValueError(f"reference receipt is not 24/24 PASS: {path}")
        for source_path, digest in receipt["code_sha256"].items():
            if _sha256((ROOT / source_path).read_bytes()) != digest:
                raise ValueError(f"run-source digest mismatch: {source_path}")

    if qiskit["corpus_sha256"] != cirq["corpus_sha256"]:
        raise ValueError("Qiskit and Cirq corpus digest differs")
    if qiskit["code_sha256"] != cirq["code_sha256"]:
        raise ValueError("Qiskit and Cirq run-source digests differ")
    qcases = {item["id"]: item for item in qiskit["cases"]}
    ccases = {item["id"]: item for item in cirq["cases"]}
    if qcases.keys() != ccases.keys():
        raise ValueError("Qiskit and Cirq circuit IDs differ")
    for case_id in qcases:
        qsource = qcases[case_id]["source"]
        csource = ccases[case_id]["source"]
        if qsource != csource or _sha256(qsource.encode("utf-8")) != qcases[case_id]["source_sha256"]:
            raise ValueError(f"exact source identity differs: {case_id}")
        if qcases[case_id]["status"] != "PASS" or ccases[case_id]["status"] != "PASS":
            raise ValueError(f"reference case failed: {case_id}")

    comparison_path = windows / "qiskit-cirq-connected-entanglement-density-final.json"
    comparison = _read_json(comparison_path)
    _verify_self_hash(comparison, "report_sha256", comparison_path)
    if comparison.get("status") != "PASS" or comparison.get("corpus_cases") != 24:
        raise ValueError("Qiskit/Cirq cross-comparison is not 24/24 PASS")
    if comparison.get("comparator_sha256") != _sha256(
        (ROOT / "tools" / "compare_connected_quantum_receipts.py").read_bytes()
    ):
        raise ValueError("cross-comparator source digest mismatch")

    for folder in (windows, linux):
        analytic_path = folder / "analytic-connected-entangled-final.json"
        analytic = _read_json(analytic_path)
        _verify_self_hash(analytic, "receipt_sha256", analytic_path)
        if analytic.get("status") != "PASS" or sorted(
            row["width"] for row in analytic["cases"]
        ) != [20, 24, 30, 40]:
            raise ValueError(f"connected GHZ analytic suite failed: {analytic_path}")
        for source_path, digest in analytic["code_sha256"].items():
            if _sha256((ROOT / source_path).read_bytes()) != digest:
                raise ValueError(f"analytic source digest mismatch: {source_path}")

    for path in (
        windows / "connected-sparse-performance-baseline.json",
        windows / "connected-sparse-performance-inplace-diagonal-experiment.json",
    ):
        report = _read_json(path)
        _verify_self_hash(report, "report_sha256", path)
        if report.get("status") != "PASS":
            raise ValueError(f"performance run did not complete: {path}")

    for path in (
        windows / "ci-acceptance-final.json",
        linux / "ci-acceptance-final.json",
    ):
        report = _read_json(path)
        if report.get("status") != "PASS":
            raise ValueError(f"isolated-install acceptance failed: {path}")

    return {
        "status": "PASS",
        "manifest_sha256": manifest["manifest_sha256"],
        "files_verified": len(checked),
        "qiskit_cases": len(qcases),
        "cirq_cases": len(ccases),
        "direct_comparison": comparison["status"],
        "analytic_widths": [20, 24, 30, 40],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.manifest.resolve()), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"EVIDENCE_INVALID: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
