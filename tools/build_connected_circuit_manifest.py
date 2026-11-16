"""Build the unkeyed integrity manifest for new connected-circuit evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "connected-circuit-frontier"
SOURCE_FILES = (
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
    "tools/ci_acceptance.py",
    "validation/connected_quantum/__init__.py",
    "validation/connected_quantum/corpus.py",
    "tests/test_connected_quantum_corpus.py",
    "tests/test_compiler_hardening.py",
    "sharkbyte_alpha/vm.py",
    "benchmarks/sb_quantum_benchmark/frontier30.py",
    "benchmarks/sb_quantum_benchmark/quantum_frontend.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=EVIDENCE / "MANIFEST.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite existing manifest: {output}")

    paths = set(SOURCE_FILES)
    for path in EVIDENCE.rglob("*"):
        if path.is_file() and path.resolve() != output:
            paths.add(path.relative_to(ROOT).as_posix())
    entries = []
    for relative in sorted(paths):
        path = (ROOT / relative).resolve()
        if ROOT.resolve() not in path.parents or not path.is_file():
            raise FileNotFoundError(f"required manifest source is missing: {relative}")
        raw = path.read_bytes()
        entries.append({
            "path": relative,
            "bytes": len(raw),
            "sha256": _sha256(raw),
        })

    manifest = {
        "schema": 1,
        "integrity_note": "Unkeyed SHA-256 detects byte changes; it does not prove authorship or correctness.",
        "files": entries,
    }
    manifest["manifest_sha256"] = _sha256(_canonical(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "status": "MANIFEST_CREATED",
        "files": len(entries),
        "manifest_sha256": manifest["manifest_sha256"],
        "path": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
