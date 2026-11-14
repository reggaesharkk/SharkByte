"""Run bounded quantum experiments and replay their saved receipts."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

from sharkbyte_alpha import __version__, quantum
from sharkbyte_alpha.cli import canonical, envelope, parse_quantum, verify

ROOT = Path(__file__).resolve().parent
FRONTIER = ROOT / "benchmarks" / "sb_quantum_benchmark"
PHASE_SOURCES = {
    name: "qubits 2; shots 1; seed 42; " + gates + " h 0; h 1; measure_all;"
    for name, gates in (
        ("Plus Bell", "h 0; cx 0 1;"), ("Minus Bell", "h 0; cx 0 1; z 0;"),
        ("Zero", ""), ("One", "x 0; x 1;"),
    )
}


def run_experiment(source, mode, support_cap=4096):
    if len(source.encode("utf-8")) > 65_536:
        raise ValueError("Source exceeds 65,536 UTF-8 bytes.")
    if mode == "quantum":
        result = quantum.evaluate(parse_quantum(source))
    elif mode == "bell-phase":
        if source != canonical(PHASE_SOURCES).decode("ascii"):
            raise ValueError("Unrecognized Bell phase circuit bundle.")
        cases = {name: quantum.evaluate(quantum.parse(body.replace(";", ";\n")))["probabilities"]
                 for name, body in PHASE_SOURCES.items()}
        zero, one = cases.pop("Zero"), cases.pop("One")
        cases["50/50 mixture"] = {label: (zero[label] + one[label]) / 2 for label in zero}
        result = {"qubits": 2, "probabilities": cases}
    elif mode == "frontier":
        if type(support_cap) is not int or support_cap not in (4096, 8192, 16384):
            raise ValueError("Frontier30 support cap must be 4096, 8192, or 16384.")
        with tempfile.TemporaryDirectory(prefix="sharkbyte-") as directory:
            path = Path(directory) / "circuit.sb"
            path.write_bytes(source.encode("utf-8"))
            process = subprocess.run(
                [sys.executable, "-B", str(FRONTIER / "frontier30.py"), str(path),
                 "--support-cap", str(support_cap)], capture_output=True, text=True, timeout=30,
            )
        if process.returncode not in (0, 1) or not process.stdout:
            raise ValueError(process.stderr.strip() or "Frontier30 produced no result.")
        result = json.loads(process.stdout)
        for key in ("source", "source_sha256", "record_sha256", "evolution_seconds"):
            del result[key]
    else:
        raise ValueError("Replay supports quantum, Frontier30, and Bell phase receipts.")
    return envelope(source, mode, result)


def read_receipt(path):
    with Path(path).open("rb") as stream:
        data = stream.read(4_194_305)
    if len(data) > 4_194_304:
        raise ValueError("Receipt exceeds 4 MiB.")
    return json.loads(data.decode("utf-8-sig"))


def replay(receipt):
    verify(receipt)
    if receipt.get("toolchain_version") != __version__:
        raise ValueError(f"Replay requires SharkByte {receipt.get('toolchain_version')}.")
    result = receipt.get("result")
    if not isinstance(result, dict):
        raise ValueError("Invalid receipt result.")
    if receipt.get("mode") == "frontier" and result.get("result") != "PASS":
        raise ValueError("Replay requires a completed Frontier30 run.")
    rerun = run_experiment(receipt["source"], receipt.get("mode"), result.get("support_cap", 4096))
    if canonical(rerun["result"]) != canonical(result):
        raise ValueError("REPLAY_MISMATCH: the recomputed result differs.")
    return "REPLAY_MATCH: all recorded result fields matched."
