"""Read-only, bounded replay of the frozen H4 candidate-v1 certificate contract.

A candidate code hash is an archival routing identifier, NEVER an authorization to
skip mathematical verification. This verifier deliberately does not import the
mutable h4_candidate.py script, so future edits to that script cannot change its
historical source decoder or its accepted script hash.
"""
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import tempfile
from time import monotonic

from . import h4_ledger
from .h3_format import require
from .h4_limits import LIMIT
from .h4_run import WorkerUnavailable, contained_worker, read

CONTRACT = "sharkbyte-xz-cx-h-candidate-v1"
MODULE = "tools.high_support.h4_candidate_archive"
SOURCE_LIMIT = 32768
EXIT = {"VERIFIED_PASS": 0, "VERIFIED_BUDGET_EXCEEDED": 1,
        "INVALID_RECORD": 2, "UNSUPPORTED": 3}
ARCHIVED_COMMIT = "1726b96a4fecf63dbec052bd0192e2741f1e653f"
ARCHIVED_CANDIDATE_SHA256 = "6f2d5a700f553e9a3c0fab0eb4e64ff1c20fd7872523f0acfd24ab6439189a69"
ARCHIVED_H4_MODULES = {
    "h3_format.py": "01a280922972b1800fcbccb947e171c7c80671e8689ba331f55e20d518734ce5",
    "h3_generate.py": "c768affe5044001466468f57611c2bbbae9e994579ec4361fdfea77a90803c83",
    "h3_verify.py": "c77d6e7d4e7aa1c3862b0597c7b5ff05f3610ddc8935399fdeb9419adbf73e8e",
    "h4_bits.py": "ab121d9ef611992665ad55842bc39c547223c372f6dc06067d861fc793619237",
    "h4_ledger.py": "1f5e033e20055ac0c619ce7c7025351a8dd8ff34955fc6e768a58fcac967f890",
    "h4_replay.py": "1ffffddaf40cf8608a26af5c3f2773cbb93d94d88a73229fedf4a82c47771d8b",
    "h4_run.py": "0ae52413548b0c2fb22422dd6a0c5b5eade835e64a552f39bd838da0c61a732b",
}
INVALID = (ValueError, TypeError, KeyError, AttributeError, RecursionError, ArithmeticError)


def canonical(value):
    # Exact formatting of candidate-v1, including its one terminal newline.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def translate_v1(source):
    """Freeze the accepted v1 source parser without importing the candidate script."""
    require(type(source) is str and len(source.encode("utf-8")) <= SOURCE_LIMIT,
            "source byte limit exceeded")
    data = h4_ledger.strict_json(source)
    require(type(data) is dict and set(data) == {
        "contract", "qubits", "gates", "initial", "budget"}, "invalid v1 source fields")
    require(source == canonical(data), "noncanonical source bytes")
    if data["contract"] != CONTRACT:
        raise h4_ledger.UnsupportedOperation("contract version")
    require(type(data["initial"]) is list, "invalid initial list")
    indices = []
    for row in data["initial"]:
        require(type(row) is list and len(row) == 3 and type(row[0]) is int,
                "invalid initial row")
        indices.append(row[0])
    require(indices == sorted(set(indices)), "noncanonical initial indices")
    budget = data["budget"]
    require(type(budget) is str and re.fullmatch(
        r"[0-9]{1,400}(?:/[0-9]{1,400})?", budget), "invalid v1 budget")
    require(str(Fraction(budget)) == budget, "noncanonical budget")
    require(type(data["gates"]) is list, "invalid gate list")
    gates = []
    for gate in data["gates"]:
        require(type(gate) is list and len(gate) == 2, "invalid v1 gate")
        gates.append([*gate, []])
    internal = canonical({"qubits": data["qubits"], "initial": data["initial"],
                          "budget": budget, "gates": gates})
    # Width, gate count, operation, wire and finite-bit validation are performed
    # by the bounded H4 source parser. No deletions are permitted by v1.
    h4_ledger.parse(internal)
    return internal


def verify(source, receipt):
    """Independently replay a known archival version; fail shut on any drift."""
    internal = translate_v1(source)
    require(type(receipt) is str and len(receipt.encode("utf-8")) <= LIMIT,
            "receipt byte limit exceeded")
    data = h4_ledger.strict_json(receipt)
    require(type(data) is dict and set(data) == {
        "contract", "source_sha256", "candidate_sha256", "ledger", "outcome"},
            "invalid archived receipt fields")
    require(receipt == canonical(data), "noncanonical receipt bytes")
    require(data["contract"] == CONTRACT, "invalid archived contract")
    require(data["candidate_sha256"] == ARCHIVED_CANDIDATE_SHA256,
            "unregistered candidate implementation hash")
    require(data["source_sha256"] == hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "source digest mismatch")
    ledger = data["ledger"]
    require(type(ledger) is dict and ledger.get("schema") == h4_ledger.SCHEMA,
            "unsupported archived ledger schema")
    require(ledger.get("modules") == ARCHIVED_H4_MODULES,
            "unregistered H4 module combination")
    # Hash equality only selects a known schema. This call must recompute
    # each bit, charge, prefix bound, final digest and budget decision.
    # h4_ledger.verify also refuses drift in its own loaded module sources.
    result = h4_ledger.verify(internal, ledger)
    outcome = {"PASS": "VERIFIED_PASS", "FAIL": "VERIFIED_BUDGET_EXCEEDED"}[result]
    require(data["outcome"] == outcome, "archived outcome mismatch")
    return outcome


def worker(source_path, receipt_path, status_path):
    try:
        result = verify(read(source_path, SOURCE_LIMIT), read(receipt_path, LIMIT))
    except h4_ledger.UnsupportedOperation:
        result = "UNSUPPORTED"
    except INVALID + (OSError, UnicodeError, MemoryError, TimeoutError):
        result = "INVALID_RECORD"
    status_path.write_text(result, encoding="ascii")


def run(source_path, receipt_path):
    deadline = monotonic() + 25
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-archive-") as folder:
        root = Path(folder)
        src, receipt, status = root/"source", root/"receipt", root/"result"
        src.write_bytes(read(source_path, SOURCE_LIMIT).encode("utf-8"))
        receipt.write_bytes(read(receipt_path, LIMIT).encode("utf-8"))
        flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
        supervisor = contained_worker(
            [sys.executable, "-B", *flags, "-m", MODULE, "--worker", "verify",
             str(src), str(receipt), str(status)],
            deadline, root/"worker.log")
        require(supervisor["exit_status"] == 0, "archive verification worker failed")
        outcome = read(status, 64)
        require(outcome in EXIT, "invalid archive verification outcome")
        return outcome


def main():
    if len(sys.argv) == 6 and sys.argv[1:3] == ["--worker", "verify"]:
        worker(*map(Path, sys.argv[3:]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify",))
    parser.add_argument("source", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    if platform.system() not in ("Windows", "Linux"):
        outcome = "UNSUPPORTED"
    else:
        try:
            outcome = run(args.source, args.receipt)
        except (WorkerUnavailable, TimeoutError, MemoryError):
            outcome = "UNSUPPORTED"
        except INVALID + (OSError, UnicodeError):
            outcome = "INVALID_RECORD"
    print(outcome)
    return EXIT[outcome]


if __name__ == "__main__":
    sys.exit(main())
