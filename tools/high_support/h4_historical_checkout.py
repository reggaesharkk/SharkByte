"""Gate 4 research: replay candidate-v1 with its pinned historical Git tree.

This is a separate, read-only archival entry point, NOT public Hadamard support.
It loads no current H4 engine module. The accepted commit is a trust anchor for
code selection; the accepted candidate must still mathematically replay its receipt.
"""
import argparse
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile

ACCEPTED_COMMIT = "1726b96a4fecf63dbec052bd0192e2741f1e653f"
ACCEPTED_FILES = {
    "tools/high_support/h4_candidate.py":
        "6f2d5a700f553e9a3c0fab0eb4e64ff1c20fd7872523f0acfd24ab6439189a69",
    "tools/high_support/h3_format.py":
        "01a280922972b1800fcbccb947e171c7c80671e8689ba331f55e20d518734ce5",
    "tools/high_support/h3_generate.py":
        "c768affe5044001466468f57611c2bbbae9e994579ec4361fdfea77a90803c83",
    "tools/high_support/h3_verify.py":
        "c77d6e7d4e7aa1c3862b0597c7b5ff05f3610ddc8935399fdeb9419adbf73e8e",
    "tools/high_support/h4_bits.py":
        "ab121d9ef611992665ad55842bc39c547223c372f6dc06067d861fc793619237",
    "tools/high_support/h4_ledger.py":
        "1f5e033e20055ac0c619ce7c7025351a8dd8ff34955fc6e768a58fcac967f890",
    "tools/high_support/h4_replay.py":
        "1ffffddaf40cf8608a26af5c3f2773cbb93d94d88a73229fedf4a82c47771d8b",
    "tools/high_support/h4_run.py":
        "0ae52413548b0c2fb22422dd6a0c5b5eade835e64a552f39bd838da0c61a732b",
    "evidence/h4-candidate/source.json":
        "9bda8fe9794ea6af6ab431ee1c6b81ccf8ad792ef1f11f5668ff7568bb761d59",
    "evidence/h4-candidate/receipt.json":
        "2d5d9f4a767cca1fe933a05f7b729efb1e72db4dbe6c0ac48e96bbd981909c33",
}
PATHS = ("tools", "benchmarks/sb_quantum_benchmark",
         "evidence/h4-candidate/source.json", "evidence/h4-candidate/receipt.json")
MAX_TAR = 3 * 1024 * 1024
MAX_ENTRIES = 256
MAX_FILES_BYTES = 2 * 1024 * 1024
SOURCE_LIMIT = 32768
RECEIPT_LIMIT = 4 * 1024 * 1024
OUTCOMES = {"VERIFIED_PASS": 0, "VERIFIED_BUDGET_EXCEEDED": 1,
            "INVALID_RECORD": 2, "UNSUPPORTED": 3}
ROOT = Path(__file__).resolve().parents[2]


class HistoryUnavailable(RuntimeError):
    """Pinned historical commit is missing from this checkout's Git object store."""


def read_bytes(path, limit):
    with Path(path).open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("input byte limit exceeded")
    return data


def historical_archive(root=ROOT):
    """Extract a fixed, small subtree from a *locally available* pinned commit."""
    try:
        found = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-t", ACCEPTED_COMMIT],
            capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HistoryUnavailable("Git history unavailable") from exc
    if found.returncode != 0 or found.stdout.strip() != "commit":
        raise HistoryUnavailable("accepted commit missing; fetch full Git history")

    command = ["git", "-C", str(root), "archive", "--format=tar",
               ACCEPTED_COMMIT, *PATHS]
    try:
        result = subprocess.run(command, capture_output=True, timeout=25,
                                check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HistoryUnavailable("pinned archive unavailable") from exc
    if result.returncode != 0:
        raise HistoryUnavailable("failed to read pinned Git archive")
    if not result.stdout or len(result.stdout) > MAX_TAR:
        raise ValueError("historical archive size limit exceeded")
    return result.stdout


def extract_pinned(archive_bytes, destination):
    """Safely materialize regular files only; never extract links or other metadata."""
    if len(archive_bytes) > MAX_TAR:
        raise ValueError("historical archive size limit exceeded")
    total = 0
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = archive.getmembers()
        if len(members) > MAX_ENTRIES:
            raise ValueError("historical entry count exceeded")
        for member in members:
            name = member.name.rstrip("/")
            path = PurePosixPath(name)
            if (not name or path.is_absolute() or
                    any(p in ("", ".", "..") for p in name.split("/")) or
                    name in seen):
                raise ValueError("unsafe historical archive path")
            seen.add(name)
            if not any(name == prefix or name.startswith(prefix + "/")
                       for prefix in ("tools", "benchmarks/sb_quantum_benchmark",
                                      "evidence/h4-candidate")):
                raise ValueError("unexpected historical archive member")
            target = Path(destination).joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile() or member.size > MAX_FILES_BYTES:
                raise ValueError("unsupported historical archive entry")
            total += member.size
            if total > MAX_FILES_BYTES:
                raise ValueError("historical extraction size limit exceeded")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("missing archived file")
            content = stream.read(member.size + 1)
            if len(content) != member.size:
                raise ValueError("truncated archived file")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    validate_snapshot(destination)


def validate_snapshot(destination):
    """Independent manifest check BEFORE running any archived Python code."""
    for path, expected in ACCEPTED_FILES.items():
        actual = hashlib.sha256((Path(destination) / path).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("accepted Git tree content mismatch: " + path)


def historical_environment():
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP",
                "PYTHONINSPECT", "PYTHONWARNINGS"):
        env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def verify(source, receipt, *, root=ROOT):
    """Return the historical CLI outcome and corresponding exit code."""
    # The archive and manifest are obtained without evaluating current H4 modules.
    source_bytes = read_bytes(source, SOURCE_LIMIT)
    receipt_bytes = read_bytes(receipt, RECEIPT_LIMIT)
    data = historical_archive(root)
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-history-") as folder:
        location = Path(folder)
        extract_pinned(data, location)
        inputs = location / "archival-inputs"
        inputs.mkdir()
        (inputs / "source.json").write_bytes(source_bytes)
        (inputs / "receipt.json").write_bytes(receipt_bytes)

        flags = ["-" + "O" * sys.flags.optimize] if sys.flags.optimize else []
        cmd = [sys.executable, "-B", *flags, "-m", "tools.high_support.h4_candidate",
               "verify", str(inputs / "source.json"), str(inputs / "receipt.json")]
        try:
            proc = subprocess.run(cmd, cwd=location, env=historical_environment(),
                                  capture_output=True, text=True, timeout=55,
                                  check=False)
        except subprocess.TimeoutExpired as exc:
            raise HistoryUnavailable("historical verifier deadline exceeded") from exc
        output = proc.stdout.strip()
        if output not in OUTCOMES or proc.returncode != OUTCOMES[output]:
            raise ValueError("historical verifier exit/output disagreement")
        return output, proc.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["verify"])
    parser.add_argument("source", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        outcome, code = verify(args.source, args.receipt)
    except HistoryUnavailable:
        outcome, code = "UNSUPPORTED", 3
    except (OSError, ValueError, tarfile.TarError, MemoryError):
        outcome, code = "INVALID_RECORD", 2
    print(outcome)
    return code


if __name__ == "__main__":
    sys.exit(main())
