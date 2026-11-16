"""Repeatable timing and Python-heap profile for connected sparse circuits."""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import io
import json
import math
import platform
import pstats
from pathlib import Path
import statistics
import struct
import sys
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for _path in (str(ROOT), str(BENCHMARK_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import sparse_backend  # noqa: E402
from validation.connected_quantum.corpus import build_cases  # noqa: E402


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _state_hash(state: dict[int, complex]) -> str:
    raw = b"".join(
        struct.pack("<Qdd", basis, value.real, value.imag)
        for basis, value in sorted(state.items())
    )
    return _sha256(raw)


def _execute(case: dict, support_cap: int, memory_budget_bytes: int):
    gates = tuple(tuple(gate) for gate in case["gates"][:case["prefix_gate_count"]])
    stats = sparse_backend.EvolutionStats()
    started = time.perf_counter()
    state = sparse_backend.evolve(
        sparse_backend.Circuit(case["width"], gates, case["id"]),
        support_cap=support_cap,
        memory_budget_bytes=memory_budget_bytes,
        max_seconds=120.0,
        stats=stats,
    )
    return state, stats, time.perf_counter() - started, len(gates)


def _mad(values: list[float], median: float) -> float:
    return statistics.median(abs(value - median) for value in values)


def _run_case(case: dict, repeats: int, warmups: int,
              support_cap: int, memory_budget_bytes: int,
              profile: bool) -> dict:
    for _ in range(warmups):
        _execute(case, support_cap, memory_budget_bytes)

    times = []
    expected_hash = None
    peak_support = 0
    gate_count = 0
    for _ in range(repeats):
        state, stats, elapsed, gate_count = _execute(
            case, support_cap, memory_budget_bytes
        )
        state_hash = _state_hash(state)
        if expected_hash is None:
            expected_hash = state_hash
        elif expected_hash != state_hash:
            raise ArithmeticError(f"{case['id']}: repeated state hash changed")
        peak_support = max(peak_support, stats.peak_support)
        times.append(elapsed)

    heap_peaks = []
    for _ in range(2):
        tracemalloc.start()
        state, stats, _, _ = _execute(case, support_cap, memory_budget_bytes)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if _state_hash(state) != expected_hash:
            raise ArithmeticError(f"{case['id']}: memory run state hash changed")
        heap_peaks.append(peak)
        peak_support = max(peak_support, stats.peak_support)

    median = statistics.median(times)
    row = {
        "id": case["id"],
        "width": case["width"],
        "seed": case["seed"],
        "source_sha256": case["source_sha256"],
        "prefix_gate_count": gate_count,
        "repeats": repeats,
        "warmups": warmups,
        "elapsed_seconds": times,
        "median_seconds": median,
        "median_absolute_deviation_seconds": _mad(times, median),
        "python_heap_peak_bytes_samples": heap_peaks,
        "python_heap_peak_bytes_max": max(heap_peaks),
        "peak_populated_states": peak_support,
        "state_sha256": expected_hash,
        "status": "PASS",
    }
    if profile:
        profiler = cProfile.Profile()
        profiler.enable()
        state, stats, _, _ = _execute(case, support_cap, memory_budget_bytes)
        profiler.disable()
        if _state_hash(state) != expected_hash:
            raise ArithmeticError(f"{case['id']}: profiled state hash changed")
        rendered = io.StringIO()
        pstats.Stats(profiler, stream=rendered).sort_stats("cumulative").print_stats(18)
        row["cprofile_top_cumulative"] = rendered.getvalue()
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--support-cap", type=int, default=65536)
    parser.add_argument("--memory-budget-mib", type=int, default=64)
    parser.add_argument("--profile-width", type=int, default=16)
    args = parser.parse_args()
    if args.repeats < 3 or args.warmups < 0:
        parser.error("use at least three timed repeats and a nonnegative warmup count")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Refusing to overwrite existing profile: {output}")

    case_map = {case["width"]: case for case in build_cases()
                if case["kind"] == "random-connected" and
                case["id"].endswith("00")}
    widths = [width for width in (12, 14, 16) if width in case_map]
    rows = []
    for width in widths:
        row = _run_case(
            case_map[width], args.repeats, args.warmups, args.support_cap,
            args.memory_budget_mib * 1024 * 1024,
            profile=(width == args.profile_width),
        )
        rows.append(row)
        print(f"PASS {width}q median={row['median_seconds']:.6f}s "
              f"heap_peak={row['python_heap_peak_bytes_max']} bytes")

    report = {
        "schema": 1,
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "workload": "new randomized connected-circuit prefix; excludes old disconnected scaling benchmark",
        "python_version": sys.version,
        "host": {
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "measurement_method": {
            "timing": "perf_counter; one warmup; median and median absolute deviation",
            "memory": "tracemalloc peak Python heap; two separate instrumented runs, excluded from timing samples",
            "profile": "cProfile cumulative top 18 functions; profiling run excluded from timing samples",
        },
        "support_cap": args.support_cap,
        "memory_budget_bytes": args.memory_budget_mib * 1024 * 1024,
        "repeats": args.repeats,
        "warmups": args.warmups,
        "code_sha256": {
            path: _sha256((ROOT / path).read_bytes())
            for path in (
                "tools/benchmark_connected_sparse.py",
                "validation/connected_quantum/corpus.py",
                "benchmarks/sb_quantum_benchmark/sparse_backend.py",
            )
        },
        "cases": rows,
    }
    report["report_sha256"] = _sha256(_canonical(report))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"{report['status']}: {len(rows)} connected cases; report {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
