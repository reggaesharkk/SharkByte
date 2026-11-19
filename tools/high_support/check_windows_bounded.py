"""Native Windows job acceptance matrix. Writes evidence only after all cases pass."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile

from tools.high_support.limit_bounded_windows import ROOT, supervise


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--architecture",choices=("ARM64","AMD64"),required=True)
    args = parser.parse_args()
    # Read the actual interpreter's PE machine type; OS architecture alone can hide emulation.
    with open(sys.executable, "rb") as image:
        image.seek(60)
        image.seek(int.from_bytes(image.read(4),"little")+4)
        machine = int.from_bytes(image.read(2),"little")
    expected = {"ARM64": 0xaa64, "AMD64": 0x8664}[args.architecture]
    if machine != expected or platform.machine().upper() != args.architecture:
        raise RuntimeError("native machine mismatch")
    source = ROOT/"examples/high_support/roundtrip_17q.sbq"
    settings = ["--support-cap","131072","--memory-mib","256","--seconds","180",
                "--interval","214","--budget","1e-10"]
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        receipt = directory/"generate-pass"
        for operation in ("generate","verify"):
            for memory, seconds, expected_status, repetitions in [
                (512,180,"pass",1),(32,180,"memory_refusal",10),(512,0.25,"timeout",10)
            ]:
                for i in range(repetitions):
                    output = directory/(operation+"-"+expected_status)
                    report = supervise(operation,source,output,
                                       settings if operation=="generate" else [str(receipt)],
                                       memory,seconds)
                    diagnostics = Path(report.pop("diagnostics"))
                    log = diagnostics/"diagnostics.log"
                    if report["status"] != expected_status:
                        raise RuntimeError((report, log.read_text() if log.exists() else ""))
                    if not (report["active_after_cleanup"] == 0 and report["total_processes"] >= 1
                            and 0 < report["peak_job_committed_bytes"] <= memory*2**20
                            and all(s["membership_verified"] for s in report["stages"])):
                        raise RuntimeError(("job accounting",report))
                    if output.exists() != (expected_status=="pass"):
                        raise RuntimeError("publication mismatch")
                    if output.exists():
                        report["output_sha256"] = sha(output)
                        if report["verified_receipt_sha256"] != sha(receipt):
                            raise RuntimeError("independent digest mismatch")
                    report["repetition"] = i+1
                    cases.append(report)
        generated = json.loads(receipt.read_bytes())
        if generated["source_sha256"] != sha(source) or generated["final_support"] != 1:
            raise RuntimeError("roundtrip fixture result mismatch")
        record = dict(final_support=generated["final_support"],
                      deletion_events=len(generated["certificate"]["events"]),python=sys.version, machine=platform.machine(), pe_machine=hex(machine),
                      windows=platform.version(), source_sha256=sha(source),receipt_sha256=sha(receipt),
                      receipt_bytes=receipt.stat().st_size,cases=cases)
    paths = [Path(__file__).resolve()] + [ROOT/"tools/high_support"/(s+".py") for s in
            ("windows_job","windows_bounded_worker","limit_bounded_windows")]
    paths += [ROOT/"benchmarks/sb_quantum_benchmark"/(s+".py") for s in
              ("bounded_support","verify_bounded","sparse_backend","frontier30","quantum_frontend")]
    record["implementation_sha256"] = {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
