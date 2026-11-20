"""H4 Gate 4c: OS-limited CLI around the unchanged Gate 4b comparator.

Research only: no candidate-v2, no public Hadamard certification, no OS attestation.
Only input snapshots and fixed-size result metadata are handled in the parent.
The independent arithmetic, pinned Git archive, and JSON replay run in a child.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import signal
import stat
import subprocess
import sys
import tempfile
import time

from . import h4_historical_checkout as history

ROOT = Path(__file__).resolve().parents[2]
MODULE = "tools.high_support.h4_compatibility_contained"
MEMORY_MIB = 256
WALL_SECONDS = 90
MAX_RESULT_BYTES = 8192
DECISIONS = {0: "COMPATIBLE", 1: "NOT_ESTABLISHED",
             2: "INVALID_RECORD", 3: "UNSUPPORTED"}


class ContainmentUnavailable(RuntimeError):
    """The comparator cannot be confined under the requested runtime contract."""


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def _decision(version_a, source_a, receipt_a, version_b, source_b, receipt_b):
    # Importing this module ONLY in the contained worker is deliberate.
    from . import h4_compatibility as h4
    try:
        report = h4.compare(version_a, history.read_bytes(source_a, history.SOURCE_LIMIT),
                            history.read_bytes(receipt_a, history.RECEIPT_LIMIT),
                            version_b, history.read_bytes(source_b, history.SOURCE_LIMIT),
                            history.read_bytes(receipt_b, history.RECEIPT_LIMIT))
        code = 0 if report["decision"] == "COMPATIBLE" else 1
    except (h4.Unsupported, history.HistoryUnavailable, MemoryError, TimeoutError) as exc:
        report, code = {"decision": "UNSUPPORTED", "reason": str(exc)[:200]}, 3
    except (ValueError, TypeError, KeyError, ArithmeticError, RecursionError,
            OSError, UnicodeError) as exc:
        report, code = {"decision": "INVALID_RECORD", "reason": str(exc)[:200]}, 2
    return {"exit_code": code, "report": report}


def _worker(arguments):
    # Parent passes six fixed positional arguments and a private output path.
    if len(arguments) != 7:
        return 4
    *inputs, output = arguments
    payload = _decision(*inputs)
    Path(output).write_bytes(_canonical(payload).encode("ascii"))
    return 0  # Deliberately independent of the compatibility decision.


def _linux_launch(command, deadline, memory_bytes, working_dir):
    import resource

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    environment = history.historical_environment()
    process = subprocess.Popen(command, cwd=ROOT, env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True,
                               preexec_fn=limits, close_fds=True)
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("deadline before wait")
        code = process.wait(timeout=remaining)
        if code != 0:
            raise ContainmentUnavailable("contained worker did not return an outcome")
        if time.monotonic() >= deadline:
            raise TimeoutError("deadline after child exit")
        return {"os_limit": "RLIMIT_AS_per_process", "limit_bytes": memory_bytes,
                "worker_exit_status": code, "worker_pid": process.pid}
    finally:
        # The comparator's bounded Git subprocesses inherit RLIMIT_AS. Terminate
        # the process group even when its direct parent already exited.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise ContainmentUnavailable("child termination unconfirmed") from exc


def _windows_launch(command, deadline, memory_bytes, working_dir):
    from .windows_job import Job

    # The lower inner cap is an empirical early-refusal margin, not a second
    # theorem that Windows peak commit cannot exceed a configured threshold.
    inner = memory_bytes - min(12 * 1024**2, memory_bytes // 2)
    job = Job(memory_bytes, inner_limit=inner)
    stage, accounting = {}, {}
    try:
        job.run(command[1:], ROOT, deadline, stage)
    finally:
        job.finish(accounting)
    if accounting.get("active_after_cleanup") != 0:
        raise ContainmentUnavailable("job descendants remain active")
    if accounting.get("peak_job_committed_bytes", memory_bytes+1) > memory_bytes:
        raise ContainmentUnavailable("outer job commit limit exceeded")
    if time.monotonic() >= deadline:
        raise TimeoutError("deadline after Windows job drain")
    return {"os_limit": "Windows_JOB_OBJECT_LIMIT_JOB_MEMORY",
            "limit_bytes": memory_bytes, "inner_limit_bytes": inner,
            "peak_job_committed_bytes": accounting["peak_job_committed_bytes"],
            "active_after_cleanup": accounting["active_after_cleanup"],
            "worker_exit_status": stage.get("exit_status", -1),
            "worker_pid": stage.get("pid")}


def _check_child_result(blob):
    if len(blob) > MAX_RESULT_BYTES:
        raise ContainmentUnavailable("child result exceeded byte cap")
    try:
        payload = json.loads(blob.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContainmentUnavailable("invalid child result encoding") from exc
    if type(payload) is not dict or set(payload) != {"exit_code", "report"}:
        raise ContainmentUnavailable("invalid child result shape")
    code, report = payload["exit_code"], payload["report"]
    if type(code) is not int or code not in DECISIONS or type(report) is not dict:
        raise ContainmentUnavailable("invalid child result category")
    if report.get("decision") != DECISIONS[code]:
        raise ContainmentUnavailable("child result and exit category disagree")
    return payload


def supervise(arguments, *, memory_mib=MEMORY_MIB, seconds=WALL_SECONDS):
    """Return (validated report, CLI code). Never execute H4 arithmetic in parent."""
    started = time.monotonic()
    if (type(memory_mib) is not int or not 32 <= memory_mib <= 1024 or
            not math.isfinite(seconds) or not 0 < seconds <= 180):
        raise ValueError("resource limits outside Gate 4c range")
    if len(arguments) != 6:
        raise ValueError("two selectors and four input paths required")
    deadline = started + seconds
    os_name = platform.system()
    if os_name not in ("Windows", "Linux"):
        return {"decision": "UNSUPPORTED", "reason": "unsupported operating system"}, 3
    try:
        with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-gate4c-") as directory:
            root = Path(directory)
            frozen = []
            bindings = {}
            for index, (name, limit) in enumerate(zip(
                (arguments[1], arguments[2], arguments[4], arguments[5]),
                (history.SOURCE_LIMIT, history.RECEIPT_LIMIT,
                 history.SOURCE_LIMIT, history.RECEIPT_LIMIT),
            )):
                # Refuse FIFOs, device nodes, sockets, directories and symlinks
                # before any blocking read in the parent. Only trusted local
                # regular-file paths are supported; concurrent writers remain open.
                if not stat.S_ISREG(Path(name).lstat().st_mode):
                    raise ValueError("Gate 4c requires regular input files")
                data = history.read_bytes(Path(name), limit)
                path = root / ("input-%d.json" % index)
                path.write_bytes(data)
                frozen.append(str(path))
                bindings["input_%d_sha256" % index] = hashlib.sha256(data).hexdigest()
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline during input snapshot")
            outcome = root / "child-result.json"
            flags = ["-" + "O" * sys.flags.optimize] if sys.flags.optimize else []
            command = [sys.executable, "-B", *flags, "-m", MODULE, "--worker",
                       arguments[0], frozen[0], frozen[1],
                       arguments[3], frozen[2], frozen[3], str(outcome)]
            memory_bytes = memory_mib * 1024**2
            if os_name == "Windows":
                containment = _windows_launch(command, deadline, memory_bytes, root)
            else:
                containment = _linux_launch(command, deadline, memory_bytes, root)
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline before result inspection")
            with outcome.open("rb") as stream:
                blob = stream.read(MAX_RESULT_BYTES + 1)
            payload = _check_child_result(blob)
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline after result inspection")
            report = dict(payload["report"],
                          containment=containment,
                          input_sha256=bindings,
                          limit_seconds=seconds,
                          elapsed_seconds=time.monotonic()-started)
            return report, payload["exit_code"]
    except (TimeoutError, ContainmentUnavailable, ChildProcessError, MemoryError,
            OSError, RuntimeError) as exc:
        return {"decision": "UNSUPPORTED", "reason": type(exc).__name__,
                "limit_seconds": seconds}, 3
    except (ValueError, TypeError) as exc:
        return {"decision": "INVALID_RECORD", "reason": str(exc)[:200]}, 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--worker":
        return _worker(args[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-mib", type=int, default=MEMORY_MIB)
    parser.add_argument("--seconds", type=float, default=WALL_SECONDS)
    for side in ("left", "right"):
        parser.add_argument(side + "_version")
        parser.add_argument(side + "_source", type=Path)
        parser.add_argument(side + "_receipt", type=Path)
    arguments = parser.parse_args(args)
    six = [arguments.left_version, str(arguments.left_source),
           str(arguments.left_receipt), arguments.right_version,
           str(arguments.right_source), str(arguments.right_receipt)]
    report, code = supervise(six, memory_mib=arguments.memory_mib, seconds=arguments.seconds)
    print(_canonical(report), end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
