"""Run the full repository test suite and write a source-bound platform record."""
import argparse
import hashlib
import io
import json
import platform
from pathlib import Path
import subprocess
import sys
import time
import unittest


ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
HASHED_PATHS=(
    "tools/high_support/check_platform_regressions.py",
    "tools/high_support/check_certified_support.py",
    "benchmarks/sb_quantum_benchmark/certified_support.py",
    "benchmarks/sb_quantum_benchmark/bounded_support.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
    "tests/test_certified_support.py",
    "README.md",
    "CLAIM_BOUNDARIES.md",
    "REPRODUCIBILITY.md",
    "docs/certified-bounded-support.md",
    "requirements-high-support.txt",
    "requirements-independent-quantum.txt",
    ".github/workflows/certified-support.yml",
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def windows_pe_machine():
    if sys.platform != "win32":
        return None
    with open(sys.executable,"rb") as stream:
        stream.seek(60)
        stream.seek(int.from_bytes(stream.read(4),"little")+4)
        return hex(int.from_bytes(stream.read(2),"little"))


def check_target(target):
    machine=platform.machine().upper()
    release=platform.release().lower()
    if target=="windows-arm64":
        if sys.platform!="win32" or machine!="ARM64" or windows_pe_machine()!="0xaa64":
            raise RuntimeError("expected native Windows ARM64 CPython")
    elif target=="ubuntu-wsl2-arm64":
        if sys.platform!="linux" or machine not in ("AARCH64","ARM64") or "microsoft" not in release:
            raise RuntimeError("expected Ubuntu WSL2 ARM64")
    return machine


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target",choices=("windows-arm64","ubuntu-wsl2-arm64"),required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    machine=check_target(args.target)
    output=args.output if args.output.is_absolute() else ROOT/args.output
    runner_output=io.StringIO()
    start=time.perf_counter()
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    result=unittest.TextTestRunner(stream=runner_output,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    if not result.wasSuccessful():
        sys.stderr.write(runner_output.getvalue())
        raise SystemExit(1)
    record=dict(
        schema="sharkbyte-platform-regression-v1",
        target=args.target,
        head_commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip(),
        python=sys.version,
        implementation=platform.python_implementation(),
        system=platform.system(),
        release=platform.release(),
        machine=machine,
        windows_pe_machine=windows_pe_machine(),
        tests_run=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
        skipped=[dict(test=str(test),reason=reason) for test,reason in result.skipped],
        elapsed_seconds=elapsed,
        status="PASS",
        sha256={path:sha256(ROOT/path) for path in HASHED_PATHS},
    )
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,indent=2)
        stream.write("\n")
    print(json.dumps({key:record[key] for key in
          ("target","head_commit","tests_run","failures","errors","elapsed_seconds","status")},indent=2))


if __name__=="__main__":
    main()
