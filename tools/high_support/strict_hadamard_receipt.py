"""Versioned strict receipt validation for H3 archives and H4 ledgers."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from . import h3_verify, h4_ledger
from .h3_format import digest, request, require, rows
from .h4_limits import LIMIT, MEMORY

SCHEMA = "sharkbyte-strict-hadamard-receipt-v1"
LEGACY = {"machine", "platform", "python", "worker_memory_bytes",
          "generate", "verify", "ledger_bytes", "ledger"}
PHASE = {"decision", "seconds", "peak_resident_bytes", "resident_metric", "supervisor"}
WINDOWS = "Windows Job Object commit cap + kill-on-close"
LINUX = "RLIMIT_AS address-space cap + parent timeout"


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def duration(value):
    return type(value) in (int, float) and 0 <= value <= 60 and math.isfinite(value)


def validate_envelope(receipt):
    require(type(receipt) is dict and set(receipt) == LEGACY, "invalid receipt fields")
    for field in ("platform", "machine", "python"):
        value = receipt[field]
        require(isinstance(value, str) and 0 < len(value) <= 256 and value.isprintable(),
                "invalid platform metadata")
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", receipt["python"]))
    windows = receipt["platform"].startswith("Windows-")
    require(windows or receipt["platform"].startswith("Linux-"), "unsupported platform label")
    require(integer(receipt["worker_memory_bytes"]) and receipt["worker_memory_bytes"] == MEMORY)
    ledger = receipt["ledger"]
    require(type(ledger) is dict and ledger.get("decision") in ("PASS", "FAIL"))
    size = len(json.dumps(ledger, indent=2, allow_nan=False).encode("utf-8"))
    require(integer(receipt["ledger_bytes"]) and receipt["ledger_bytes"] == size,
            "ledger size mismatch")
    for name in ("generate", "verify"):
        phase = receipt[name]
        require(type(phase) is dict and set(phase) == PHASE)
        require(phase["decision"] == ledger["decision"], "phase/ledger decision mismatch")
        require(duration(phase["seconds"]) and integer(phase["peak_resident_bytes"], 1))
        expected_metric = "Windows PeakWorkingSetSize" if windows else "getrusage(RUSAGE_SELF).ru_maxrss"
        require(phase["resident_metric"] == expected_metric, "resident metric/platform mismatch")
        supervisor = phase["supervisor"]
        keys = {"elapsed_wall_seconds", "exit_status", "containment"}
        if windows:
            keys |= {"active_after_cleanup", "peak_job_committed_bytes"}
        require(type(supervisor) is dict and set(supervisor) == keys)
        require(duration(supervisor["elapsed_wall_seconds"])
                and phase["seconds"] <= supervisor["elapsed_wall_seconds"])
        require(integer(supervisor["exit_status"]) and supervisor["exit_status"] == 0)
        require(supervisor["containment"] == (WINDOWS if windows else LINUX))
        if windows:
            require(integer(supervisor["active_after_cleanup"]) and supervisor["active_after_cleanup"] == 0)
            peak = supervisor["peak_job_committed_bytes"]
            require(integer(peak, 1) and peak <= MEMORY)


def validate(source, receipt):
    validate_envelope(receipt)
    ledger = receipt["ledger"]
    if ledger.get("schema") == h4_ledger.SCHEMA:
        decision = h4_ledger.verify(source, ledger)
        bits = "DETERMINISTIC_REPLAY"
    else:
        size, _, _, _ = request(source)
        require(isinstance(ledger.get("steps"), list) and len(ledger["steps"]) <= 64)
        for event in ledger["steps"]:
            post = rows(event["post"], size)
            require(list(post) == sorted(post) and all(post.values()),
                    "noncanonical sparse post-state")
        decision = h3_verify.verify(source, ledger)
        bits = "RECORDED_ONLY"
    return {"decision": decision, "mathematical_replay": "PASS", "canonical": True,
            "bit_replay": bits, "execution_provenance": "UNAUTHENTICATED"}


def seal(source, receipt):
    validate(source, receipt)
    return {"schema": SCHEMA, "receipt": receipt, "content_sha256": digest(receipt)}


def verify(source, wrapper, *, expected_digest=None):
    require(type(wrapper) is dict and set(wrapper) == {"schema", "receipt", "content_sha256"}
            and wrapper["schema"] == SCHEMA, "invalid strict wrapper")
    observed = digest(wrapper["receipt"])
    require(wrapper["content_sha256"] == observed, "receipt content digest mismatch")
    if expected_digest is not None:
        require(observed == expected_digest, "trusted content digest mismatch")
    result = validate(source, wrapper["receipt"])
    return dict(result, content_binding="EXTERNALLY_PINNED" if expected_digest is not None
                else "SELF_REPORTED_DIGEST")


def read(path, maximum):
    with path.open("rb") as stream:
        data = stream.read(maximum+1)
    require(len(data) <= maximum, "input byte limit exceeded")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "seal", "verify"))
    parser.add_argument("source", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-digest", help="Trusted raw SHA-256 in archive mode, content SHA-256 in verify mode")
    args = parser.parse_args()
    try:
        source = read(args.source, 32768).decode("utf-8")
        raw = read(args.receipt, LIMIT)
        data = h4_ledger.strict_json(raw.decode("utf-8"))
        if args.mode == "archive":
            if args.expected_digest is not None:
                require(hashlib.sha256(raw).hexdigest() == args.expected_digest,
                        "trusted archive digest mismatch")
            result = dict(validate(source, data), content_binding="EXTERNALLY_PINNED"
                          if args.expected_digest is not None else "UNPINNED_ARCHIVE")
        elif args.mode == "seal":
            require(args.expected_digest is None, "digest pin applies only to verification")
            result = seal(source, data)
        else:
            result = verify(source, data, expected_digest=args.expected_digest)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RecursionError, ArithmeticError) as exc:
        parser.exit(1, f"INVALID: {exc}\n")


if __name__ == "__main__":
    main()
