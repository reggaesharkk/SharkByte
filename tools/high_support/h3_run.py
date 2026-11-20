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
from .h3_generate import generate
from .h3_verify import verify

MODULE = "tools.high_support.h3_run"
MEMORY = 256 * 1024**2
LIMIT = 4 * 1024**2


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
        ledger = json.loads(read(ledger_path, LIMIT))
        if mode == "receipt":
            ledger = ledger["ledger"]
        decision = verify(source, ledger)
    peak, method = _worker_peak_rss()
    write(report_path, {"decision": decision, "seconds": perf_counter()-start,
                        "peak_resident_bytes": peak, "resident_metric": method})


def run(source_path, output):
    deadline = monotonic() + 60
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h3-") as directory:
        root = Path(directory)
        frozen = root/"source.json"
        frozen.write_bytes(read(source_path, 32768).encode("utf-8"))
        ledger = root/"ledger.json"
        report = {"machine": platform.machine(), "platform": platform.platform(),
                  "python": platform.python_version(), "worker_memory_bytes": MEMORY}
        for phase in ("generate", "verify"):
            stats = root/(phase+".json")
            flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
            supervisor = _run_worker([sys.executable, "-B", *flags, "-m", MODULE,
                                      "--worker", phase, str(frozen), str(ledger), str(stats)],
                                     min(deadline, monotonic()+25), MEMORY, root/"worker.log")
            require(supervisor["exit_status"] == 0, "worker failed")
            report[phase] = dict(json.loads(read(stats, LIMIT)), supervisor=supervisor)
        payload = read(ledger, LIMIT)
        report["ledger_bytes"] = ledger.stat().st_size
        report["ledger"] = json.loads(payload)
        require(report["generate"]["decision"] == report["verify"]["decision"])
        _atomic_publish(output.resolve(), json.dumps(report, indent=2)+"\n", deadline=deadline)
        return report["verify"]["decision"]


def replay(source_path, receipt_path):
    deadline = monotonic() + 25
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h3-replay-") as directory:
        root = Path(directory)
        source = root/"source.json"
        source.write_bytes(read(source_path, 32768).encode("utf-8"))
        wrapper = read(receipt_path, LIMIT)
        receipt = root/"receipt.json"
        receipt.write_bytes(wrapper.encode("utf-8"))
        stats = root/"stats.json"
        flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
        supervisor = _run_worker([sys.executable, "-B", *flags, "-m", MODULE,
                                  "--worker", "receipt", str(source), str(receipt), str(stats)],
                                 deadline, MEMORY, root/"worker.log")
        require(supervisor["exit_status"] == 0, "replay worker failed")
        return json.loads(read(stats, LIMIT))["decision"]


def main():
    if len(sys.argv) == 6 and sys.argv[1] == "--worker":
        worker(sys.argv[2], *map(Path, sys.argv[3:]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.replay:
        decision = replay(args.source, args.output)
    else:
        decision = run(args.source, args.output)
    print(decision)
    return int(decision != "PASS")


if __name__ == "__main__":
    sys.exit(main())
