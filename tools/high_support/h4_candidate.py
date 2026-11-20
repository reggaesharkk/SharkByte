"""Opt-in, source-checkout certificate candidate for bounded X/Z/CX/H."""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import struct
import sys
import tempfile
from time import monotonic

from . import h4_ledger
from .frontier_scaling import _atomic_publish
from .h3_format import require
from .h4_limits import LIMIT
from .h4_run import INVALID, OUTCOMES, WorkerUnavailable, contained_worker, read

CONTRACT = "sharkbyte-xz-cx-h-candidate-v1"
MODULE = "tools.high_support.h4_candidate"
SOURCE_LIMIT = 32768
EXIT = {"VERIFIED_PASS": 0, "VERIFIED_BUDGET_EXCEEDED": 1,
        "INVALID_RECORD": 2, "UNSUPPORTED": 3}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def binary64_word(value):
    """Encode a finite built-in Python float without numeric coercion."""
    require(type(value) is float and math.isfinite(value), "expected finite built-in float")
    if (sys.float_info.radix, sys.float_info.mant_dig, sys.float_info.max_exp) != (2, 53, 1024):
        raise h4_ledger.UnsupportedOperation("float format")
    return struct.pack(">d", value).hex()


def encode_source(qubits, gates, initial, budget):
    """Build canonical source from gate lists, indexed float pairs and a Fraction."""
    require(type(budget) is Fraction and budget >= 0, "expected nonnegative Fraction")
    require(type(initial) is dict and all(type(i) is int for i in initial))
    data = {"contract": CONTRACT, "qubits": qubits, "gates": gates,
            "initial": [[i, binary64_word(real), binary64_word(imag)]
                        for i, (real, imag) in sorted(initial.items())],
            "budget": str(budget)}
    source = canonical(data)
    translate(source)
    return source


def translate(source):
    require(len(source.encode("utf-8")) <= SOURCE_LIMIT, "source byte limit exceeded")
    data = h4_ledger.strict_json(source)
    require(type(data) is dict and set(data) == {"contract", "qubits", "gates", "initial", "budget"})
    require(source == canonical(data), "noncanonical source bytes")
    if data["contract"] != CONTRACT:
        raise h4_ledger.UnsupportedOperation("contract version")
    require(type(data["initial"]) is list)
    indices = []
    for row in data["initial"]:
        require(type(row) is list and len(row) == 3 and type(row[0]) is int)
        indices.append(row[0])
    require(indices == sorted(set(indices)), "noncanonical initial indices")
    raw_budget = data["budget"]
    require(type(raw_budget) is str and re.fullmatch(r"[0-9]{1,400}(?:/[0-9]{1,400})?", raw_budget))
    require(str(Fraction(raw_budget)) == raw_budget, "noncanonical budget")
    require(type(data["gates"]) is list)
    gates = []
    for gate in data["gates"]:
        require(type(gate) is list and len(gate) == 2)
        gates.append([*gate, []])
    internal = canonical({"qubits": data["qubits"], "initial": data["initial"],
                          "budget": raw_budget, "gates": gates})
    h4_ledger.parse(internal)
    return internal


def binding(source):
    script = Path(__file__).read_text(encoding="utf-8").encode("utf-8")
    return {"contract": CONTRACT, "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "candidate_sha256": hashlib.sha256(script).hexdigest()}


def generate(source):
    ledger = h4_ledger.generate(translate(source))
    return canonical(dict(binding(source), ledger=ledger, outcome=OUTCOMES[ledger["decision"]]))


def verify(source, receipt):
    internal = translate(source)
    require(len(receipt.encode("utf-8")) <= LIMIT, "receipt byte limit exceeded")
    data = h4_ledger.strict_json(receipt)
    require(type(data) is dict and set(data) == {
        "contract", "source_sha256", "candidate_sha256", "ledger", "outcome"})
    require(receipt == canonical(data), "noncanonical receipt bytes")
    require(all(data[key] == value for key, value in binding(source).items()), "binding mismatch")
    decision = OUTCOMES[h4_ledger.verify(internal, data["ledger"])]
    require(data["outcome"] == decision, "outcome mismatch")
    return decision


def worker(mode, source_path, receipt_path, status_path):
    try:
        source = read(source_path, SOURCE_LIMIT)
        if mode == "generate":
            receipt = generate(source)
            require(len(receipt.encode("utf-8")) <= LIMIT, "receipt byte limit exceeded")
            receipt_path.write_bytes(receipt.encode("utf-8"))
            result = h4_ledger.strict_json(receipt)["outcome"]
        else:
            require(mode == "verify")
            result = verify(source, read(receipt_path, LIMIT))
    except (h4_ledger.UnsupportedOperation, MemoryError, TimeoutError):
        result = "UNSUPPORTED"
    except INVALID + (OSError,) as exc:
        unsupported = str(exc) in {"width outside experiment domain", "gate limit exceeded",
                                   "generation deadline", "replay deadline"}
        overflow = mode == "generate" and str(exc) in {"binary64 overflow", "nonfinite binary64"}
        result = "UNSUPPORTED" if unsupported or overflow else "INVALID_RECORD"
    status_path.write_text(result, encoding="ascii")


def run(mode, source_path, output):
    deadline = monotonic() + 60
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-candidate-") as temp:
        root = Path(temp)
        source, receipt = root/"source", root/"receipt"
        source.write_bytes(read(source_path, SOURCE_LIMIT).encode("utf-8"))
        if mode == "verify":
            receipt.write_bytes(read(output, LIMIT).encode("utf-8"))
        result = None
        modes = ("generate", "verify") if mode == "generate" else ("verify",)
        flags = ["-" + "O"*sys.flags.optimize] if sys.flags.optimize else []
        for phase in modes:
            status = root/(phase+".status")
            supervisor = contained_worker(
                [sys.executable, "-B", *flags, "-m", MODULE, "--worker",
                 phase, str(source), str(receipt), str(status)],
                min(deadline, monotonic()+25), root/"worker.log")
            require(supervisor["exit_status"] == 0, "worker failed")
            outcome = read(status, 64)
            require(outcome in EXIT, "invalid worker status")
            if EXIT[outcome] >= 2:
                return outcome
            require(result is None or result == outcome, "independent replay disagreed")
            result = outcome
        if mode == "generate":
            _atomic_publish(output.absolute(), read(receipt, LIMIT), deadline=deadline)
        return result


def main():
    if len(sys.argv) == 6 and sys.argv[1] == "--worker":
        worker(sys.argv[2], *map(Path, sys.argv[3:]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    if platform.system() not in {"Windows", "Linux"}:
        outcome = "UNSUPPORTED"
    else:
        try:
            outcome = run(args.mode, args.source, args.receipt)
        except (WorkerUnavailable, TimeoutError, MemoryError):
            outcome = "UNSUPPORTED"
        except INVALID + (OSError,):
            outcome = "INVALID_RECORD"
    print(outcome)
    return EXIT[outcome]


if __name__ == "__main__":
    sys.exit(main())
