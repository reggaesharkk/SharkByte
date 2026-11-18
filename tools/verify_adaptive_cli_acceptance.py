"""Verify and replay the three opt-in adaptive CLI acceptance receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


CASES = {
    "ghz20-completed": {"budget": 256, "status": "COMPLETED", "exit": 0,
                         "fixture": "examples/high_support/adaptive_sparse_ghz_20q.sbq"},
    "random-connected20-dense-switch": {
        "budget": 256, "status": "COMPLETED", "exit": 0,
        "fixture": "examples/high_support/random_connected_20q.sbq",
        "transition": {"from": "sparse-dict", "to": "dense-complex128",
                       "gate_index": 16, "support": 65536}},
    "random-connected20-resource-stop": {
        "budget": 1, "status": "RESOURCE_STOP", "exit": 1,
        "fixture": "examples/high_support/random_connected_20q.sbq",
        "gate_index": 10},
}


def verify_record(path: Path, case: str, expected: dict) -> dict:
    raw = path.read_bytes()
    record = json.loads(raw)
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    if record.get("schema") != 1 or sha256(canonical(body)) != record.get("record_sha256"):
        raise ValueError(f"{path.name}: record digest mismatch")
    source = record.get("source")
    if not isinstance(source, str):
        raise ValueError(f"{path.name}: source is not text")
    source_hash = sha256(source.encode("utf-8"))
    if source_hash != record.get("source_sha256"):
        raise ValueError(f"{path.name}: source digest mismatch")
    fixture = Path(expected["fixture"]).read_bytes()
    if source.encode("utf-8") != fixture:
        raise ValueError(f"{path.name}: embedded source differs from {expected['fixture']}")
    result = record.get("result", {})
    if result.get("status") != expected["status"]:
        raise ValueError(f"{path.name}: unexpected status {result.get('status')!r}")
    if result.get("backend") != "auto" or result.get("memory_budget_bytes") != expected["budget"] * 1024**2:
        raise ValueError(f"{path.name}: backend or memory budget mismatch")
    if case == "random-connected20-dense-switch":
        transitions = result.get("transitions", [])
        if len(transitions) != 1 or any(
                transitions[0].get(key) != value
                for key, value in expected["transition"].items()):
            raise ValueError(f"{path.name}: expected gate-16 dense transition not found")
    if case == "random-connected20-resource-stop" and result.get("gate_index") != expected["gate_index"]:
        raise ValueError(f"{path.name}: resource stop gate index mismatch")
    return {"receipt_sha256": sha256(raw), "record_sha256": record["record_sha256"],
            "source_sha256": source_hash, "result": result, "source": source}


def replay(receipt_path: Path, case: str, expected: dict) -> dict:
    source = json.loads(receipt_path.read_text(encoding="utf-8"))["source"]
    with tempfile.TemporaryDirectory(prefix="sharkbyte-acceptance-") as temp:
        work = Path(temp)
        source_path, output_path = work / "input.sbq", work / "replay.json"
        source_path.write_text(source, encoding="utf-8", newline="\n")
        command = [sys.executable, "-m", "sharkbyte_alpha", "run", str(source_path),
                   "--mode", "quantum", "--backend", "auto", "--memory-mib",
                   str(expected["budget"]), "--output", str(output_path)]
        started = time.perf_counter()
        process = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True, text=True, check=False)
        elapsed = time.perf_counter() - started
        if process.returncode != expected["exit"]:
            raise ValueError(f"{case}: replay exit {process.returncode}, expected {expected['exit']}; "
                             f"stderr={process.stderr.strip()}")
        generated = json.loads(output_path.read_text(encoding="utf-8"))
        original = json.loads(receipt_path.read_text(encoding="utf-8"))
        if generated != original:
            raise ValueError(f"{case}: replay record differs from the original receipt")
        return {"status": "PASS", "exit_code": process.returncode,
                "record_sha256": generated["record_sha256"],
                "single_replay_wall_seconds": round(elapsed, 6)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    numpy_version = None
    try:
        import numpy
        numpy_version = numpy.__version__
    except ImportError:
        pass
    report = {
        "schema": 1,
        "status": "PASS",
        "scope": "Receipt integrity and deterministic CLI replay; not a benchmark or a correctness proof.",
        "environment": {"system": platform.system(), "release": platform.release(),
                        "architecture": platform.machine(), "python": platform.python_version(),
                        "numpy": numpy_version, "sys_platform": sys.platform},
        "cases": {},
    }
    for case, expected in CASES.items():
        path = args.receipt_dir / f"{case}.json"
        verified = verify_record(path, case, expected)
        replayed = replay(path, case, expected)
        report["cases"][case] = {key: value for key, value in verified.items() if key != "source"}
        report["cases"][case]["replay"] = replayed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "environment": report["environment"],
                      "cases": {name: value["replay"] for name, value in report["cases"].items()}},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
