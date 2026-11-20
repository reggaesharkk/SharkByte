"""Run generation and replay in separate resource-limited processes."""
import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
from time import monotonic, perf_counter

from .frontier_scaling import _atomic_publish, _run_worker, _worker_peak_rss
from .h3_format import require
from .h4_ledger import UnsupportedOperation, generate, strict_json, verify
from .h4_limits import LIMIT, MEMORY
from . import strict_hadamard_receipt as receipts

MODULE = "tools.high_support.h4_run"
OUTCOMES = {"PASS": "VERIFIED_PASS", "FAIL": "VERIFIED_BUDGET_EXCEEDED"}
INVALID = (ValueError, TypeError, KeyError, AttributeError, RecursionError, ArithmeticError)


class WorkerUnavailable(RuntimeError):
    """Containment could not complete a worker within the runtime contract."""


def contained_worker(command, deadline, diagnostics):
    try:
        return _run_worker(command, deadline, MEMORY, diagnostics)
    except (OSError, RuntimeError, MemoryError) as exc:
        raise WorkerUnavailable(str(exc)) from exc


def read(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, "input byte limit exceeded")
    return data.decode("utf-8")


def write(path, data):
    encoded = json.dumps(data, indent=2, allow_nan=False)
    require(len(encoded) <= LIMIT)
    path.write_bytes(encoded.encode("utf-8"))


def worker(mode, source_path, ledger_path, report_path):
    source = read(source_path, 32768)
    start = perf_counter()
    if mode == "generate":
        ledger = generate(source)
        write(ledger_path, ledger)
        decision = ledger["decision"]
    else:
        ledger = strict_json(read(ledger_path, LIMIT))
        if mode == "receipt":
            result = (receipts.verify(source, ledger) if isinstance(ledger, dict)
                      and "receipt" in ledger else receipts.validate(source, ledger))
            decision = result["decision"]
        elif mode in ("ledger", "verify"):
            decision = verify(source, ledger)
        else:
            raise ValueError("unknown worker mode")
    peak, method = _worker_peak_rss()
    write(report_path, {"decision": decision, "seconds": perf_counter()-start,
                        "peak_resident_bytes": peak, "resident_metric": method})


def run(source_path, output):
    deadline = monotonic() + 60
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-") as directory:
        root = Path(directory)
        frozen = root/"source.json"
        frozen.write_bytes(read(source_path, 32768).encode("utf-8"))
        ledger = root/"ledger.json"
        report = {"machine": platform.machine(), "platform": platform.platform(),
                  "python": platform.python_version(), "worker_memory_bytes": MEMORY}
        for phase in ("generate", "verify"):
            stats = root/(phase+".json")
            flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
            supervisor = contained_worker([sys.executable, "-B", *flags, "-m", MODULE,
                                      "--worker", phase, str(frozen), str(ledger), str(stats)],
                                     min(deadline, monotonic()+25), root/"worker.log")
            require(supervisor["exit_status"] == 0, "worker failed")
            phase_result = json.loads(read(stats, LIMIT))
            if phase_result["decision"] not in OUTCOMES:
                return phase_result["decision"]
            report[phase] = dict(phase_result, supervisor=supervisor)
        payload = read(ledger, LIMIT)
        report["ledger_bytes"] = ledger.stat().st_size
        report["ledger"] = json.loads(payload)
        require(report["generate"]["decision"] == report["verify"]["decision"])
        receipts.validate_envelope(report)
        serialized = json.dumps(report, indent=2, allow_nan=False)+"\n"
        require(len(serialized.encode("utf-8")) <= LIMIT, "receipt byte limit exceeded")
        _atomic_publish(output.resolve(), serialized, deadline=deadline)
        return report["verify"]["decision"]


def replay(source_path, receipt_path, *, ledger_only=False):
    deadline = monotonic() + 25
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-replay-") as directory:
        root = Path(directory)
        source = root/"source.json"
        source.write_bytes(read(source_path, 32768).encode("utf-8"))
        wrapper = read(receipt_path, LIMIT)
        receipt = root/"receipt.json"
        receipt.write_bytes(wrapper.encode("utf-8"))
        stats = root/"stats.json"
        flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
        supervisor = contained_worker([sys.executable, "-B", *flags, "-m", MODULE,
                                  "--worker", "ledger" if ledger_only else "receipt",
                                  str(source), str(receipt), str(stats)],
                                 deadline, root/"worker.log")
        require(supervisor["exit_status"] == 0, "replay worker failed")
        return json.loads(read(stats, LIMIT))["decision"]


def main():
    if len(sys.argv) == 6 and sys.argv[1] == "--worker":
        mode = sys.argv[2]
        try:
            worker(mode, *map(Path, sys.argv[3:]))
        except INVALID + (MemoryError,) as exc:
            if (isinstance(exc, MemoryError) or str(exc) in ("replay deadline", "generation deadline")
                    or mode == "generate" and (isinstance(exc, UnsupportedOperation)
                    or str(exc) in ("binary64 overflow", "nonfinite binary64",
                                    "width outside experiment domain", "gate limit exceeded"))):
                outcome = "UNSUPPORTED"
            else:
                outcome = "INVALID_RECORD"
            write(Path(sys.argv[5]), {"decision": outcome})
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--replay", action="store_true", help="validate the complete receipt")
    modes.add_argument("--ledger-only", action="store_true", help="verify a bare ledger without an envelope")
    args = parser.parse_args()
    if platform.system() not in ("Windows", "Linux"):
        print("UNSUPPORTED")
        return 3
    try:
        if args.replay or args.ledger_only:
            decision = replay(args.source, args.output, ledger_only=args.ledger_only)
        else:
            decision = run(args.source, args.output)
    except (WorkerUnavailable, TimeoutError, MemoryError):
        decision = "UNSUPPORTED"
    except INVALID + (OSError,):
        decision = "INVALID_RECORD"
    print(OUTCOMES.get(decision, decision))
    return {"PASS": 0, "FAIL": 1, "UNSUPPORTED": 3}.get(decision, 2)


if __name__ == "__main__":
    sys.exit(main())
