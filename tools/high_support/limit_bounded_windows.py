"""Publish a validated bounded receipt or verification result under a Windows Job Object."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time

from tools.high_support.windows_job import Job

ROOT = Path(__file__).resolve().parents[2]


def supervise(operation, source, destination, arguments, commit_mib, seconds):
    start = time.monotonic()
    if not 0 < seconds <= 86400 or not math.isfinite(seconds) or not 0 < commit_mib < 2**32:
        raise ValueError("invalid wall or commit limit")
    if operation not in ("generate","verify"):
        raise ValueError("unknown operation")
    deadline = start + seconds
    destination = Path(destination).absolute()
    source = Path(source).resolve(strict=True)
    if destination.exists():
        raise FileExistsError(destination)
    if operation == "verify":
        if len(arguments) != 1:
            raise ValueError("verify requires a receipt")
        arguments = [str(Path(arguments[0]).resolve(strict=True))]
    directory = Path(tempfile.mkdtemp(prefix=".bounded-",dir=destination.parent))
    report = dict(operation=operation, commit_limit_bytes=commit_mib*2**20, seconds=seconds,
                  status="failed", stages=[], diagnostics=str(directory))
    publication_stat = None
    try:
        limit = report["commit_limit_bytes"]
        report["inner_commit_limit_bytes"] = limit - min(12*2**20, limit//2)
        job = Job(limit, inner_limit=report["inner_commit_limit_bytes"])
        try:
            phases = [(operation, arguments)]
            if operation == "generate":
                phases.append(("validate", []))
            phases.append(("publish",[str(destination)]))
            for phase, args in phases:
                stage = dict(phase=phase)
                report["stages"].append(stage)
                if phase == "publish":
                    publication_stat = (directory/"completed").stat()
                job.run(["-m","tools.high_support.windows_bounded_worker",phase,directory,
                         source,*args],ROOT,deadline,stage)
                if phase in ("validate","verify"):
                    report["verified_receipt_sha256"] = (directory/"receipt.sha256").read_text()
            report["published_seconds"] = time.monotonic()-start
        finally:
            job.finish(report)
        if report["peak_job_committed_bytes"] > limit:
            raise RuntimeError("measured outer job peak exceeded requested limit")
        report["status"] = "pass"
    except TimeoutError as exc:
        report.update(status="timeout", error=str(exc))
    except ChildProcessError as exc:
        report.update(status="memory_refusal" if exc.args==(86,) else "worker_failed",
                      error=str(exc))
    except Exception as exc:
        report["error"] = repr(exc)
    finally:
        stage = directory/"completed"
        if report["status"] != "pass" and publication_stat and destination.exists():
            if os.path.samestat(destination.stat(), publication_stat):
                destination.unlink()
        for name in ("completed","input.json"):
            (directory/name).unlink(missing_ok=True)
        report["elapsed_seconds"] = time.monotonic()-start
        (directory/"supervisor.json").write_text(json.dumps(report),encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit-mib",type=int,required=True)
    parser.add_argument("--seconds",type=float,required=True)
    parser.add_argument("operation",choices=("generate","verify"))
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path)
    parser.add_argument("arguments",nargs=argparse.REMAINDER)
    args = parser.parse_args()
    report = supervise(args.operation,args.source,args.destination,args.arguments,args.commit_mib,args.seconds)
    print(json.dumps(report))
    sys.exit(0 if report["status"]=="pass" else 1)
