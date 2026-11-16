"""Repeatable per-process comparison of sparse, dense, and adaptive exact backends."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
for path in (ROOT, BENCH, ROOT / "tools" / "high_support"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from frontier30 import load_circuit
from validation.high_support.common import canonical_json, gate_descriptors, sha256

CASES = ("sparse_ghz_20q", "intermediate_20q", "random_connected_20q")
BACKENDS = ("sparse", "dense", "adaptive")


def _source_for_case(case: str) -> bytes:
    source_names = {
        "sparse_ghz_20q": "adaptive_sparse_ghz_20q.sbq",
        "intermediate_20q": "adaptive_intermediate_20q.sbq",
        "random_connected_20q": "random_connected_20q.sbq",
    }
    if case not in source_names:
        raise ValueError(f"unsupported case: {case}")
    return (ROOT / "examples" / "high_support" / source_names[case]).read_bytes()


def _peak_rss_bytes():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                       ctypes.byref(counters), counters.cb)
        return int(counters.PeakWorkingSetSize) if ok else None
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * (1024 if platform.system() != "Darwin" else 1))
    except (ImportError, OSError):
        return None


def _vector(state, qubits):
    if isinstance(state, dict):
        vector = np.zeros(1 << qubits, dtype=np.complex128)
        for basis, amplitude in state.items():
            vector[basis] = amplitude
        return vector
    return np.asarray(state, dtype=np.complex128)


def _worker(args):
    from adaptive_statevector import AdaptiveStats, evolve_adaptive
    from dense_statevector import evolve as dense_evolve
    from sparse_backend import (ESTIMATED_BYTES_PER_AMPLITUDE, EvolutionStats,
                                evolve as sparse_evolve)

    setup_started = time.perf_counter()
    source = args.source.read_bytes()
    circuit, parsed_hash = load_circuit(args.source)
    setup_seconds = time.perf_counter() - setup_started
    if parsed_hash != sha256(source):
        raise RuntimeError("parsed source digest differs from exact input bytes")
    support_cap = 1 << circuit.qubits
    memory_budget = support_cap * ESTIMATED_BYTES_PER_AMPLITUDE
    initialization_seconds = []
    evolution_seconds = []
    api_call_seconds = []
    warmup = None
    final = None
    adaptive_stats = None

    for run_index in range(args.warmups + args.repetitions):
        gc.collect()
        init_started = time.perf_counter()
        if args.backend == "sparse":
            initial = {0: 1.0 + 0.0j}
        elif args.backend == "dense":
            initial = np.zeros(1 << circuit.qubits, dtype=np.complex128)
            initial[0] = 1.0 + 0.0j
        else:
            initial = None
        init_external = time.perf_counter() - init_started
        call_started = time.perf_counter()
        if args.backend == "sparse":
            run_stats = EvolutionStats()
            final = sparse_evolve(
                circuit, support_cap=support_cap, memory_budget_bytes=memory_budget,
                max_seconds=240, stats=run_stats, initial_state=initial)
            evo_seconds = time.perf_counter() - call_started
            measured_init = init_external
        elif args.backend == "dense":
            final = dense_evolve(circuit.qubits, circuit.gates,
                                 initial_state=initial, copy_initial_state=False)
            evo_seconds = time.perf_counter() - call_started
            measured_init = init_external
        else:
            adaptive_stats = AdaptiveStats()
            final = evolve_adaptive(circuit, support_cap=support_cap,
                                    memory_budget_bytes=memory_budget,
                                    max_seconds=240, stats=adaptive_stats)
            evo_seconds = adaptive_stats.evolution_seconds
            measured_init = adaptive_stats.initialization_seconds
        call_seconds = time.perf_counter() - call_started
        if run_index < args.warmups:
            warmup = {"initialization_seconds": measured_init,
                      "evolution_seconds": evo_seconds,
                      "api_call_seconds": call_seconds}
        else:
            initialization_seconds.append(measured_init)
            evolution_seconds.append(evo_seconds)
            api_call_seconds.append(call_seconds)

    vector = _vector(final, circuit.qubits)
    normalization = float(np.vdot(vector, vector).real)
    exact_support = int(np.count_nonzero(vector))
    vector_path = args.output.with_suffix(".npy")
    np.save(vector_path, np.ascontiguousarray(vector, dtype=np.dtype("<c16")), allow_pickle=False)
    digest = sha256(vector_path.read_bytes())
    vector_digest = sha256(np.ascontiguousarray(vector, dtype=np.dtype("<c16")).tobytes())
    result = {
        "schema": 1, "status": "PASS", "case": args.case, "backend": args.backend,
        "qubits": circuit.qubits, "gate_count": len(circuit.gates),
        "source_sha256": parsed_hash, "gate_sequence": [list(g) for g in circuit.gates],
        "gate_sequence_sha256": sha256(canonical_json(gate_descriptors(circuit.gates))),
        "source_setup_seconds": setup_seconds,
        "warmup": warmup, "repetitions": args.repetitions,
        "initialization_seconds": initialization_seconds,
        "evolution_seconds": evolution_seconds,
        "api_call_seconds": api_call_seconds,
        "median_initialization_seconds": statistics.median(initialization_seconds),
        "median_evolution_seconds": statistics.median(evolution_seconds),
        "median_api_call_seconds": statistics.median(api_call_seconds),
        "peak_rss_bytes_process_lifetime": _peak_rss_bytes(),
        "active_amplitudes_exact_nonzero": exact_support,
        "normalization": normalization,
        "vector_sha256_little_endian_complex128": vector_digest,
        "npy_sha256": digest,
        "numpy_version": np.__version__, "python": platform.python_version(),
        "host": platform.platform(), "architecture": platform.machine(),
        "processor": platform.processor(),
    }
    if adaptive_stats:
        result["representation"] = adaptive_stats.representation
        result["peak_support"] = adaptive_stats.peak_support
        result["peak_estimated_bytes"] = adaptive_stats.peak_estimated_bytes
        result["transitions"] = adaptive_stats.transitions
        result["policy"] = {"dense_enter_density": 0.12, "dense_leave_density": 0.04,
                             "sparse_bytes_per_amplitude": 512,
                             "dense_peak_bytes_per_basis": 48,
                             "silent_pruning": False}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _reference_receipts(case, source_hash, gate_hash, gate_count):
    if case != "random_connected_20q":
        return {"method": "exact analytic support/probability invariants for structured circuit"}
    folder = ROOT / "evidence" / "high_support_connected" / "final_current" / "windows_arm64" / "random_20"
    names = ("random_connected_20q_comparison.json", "random_connected_20q_qiskit.json",
             "random_connected_20q_cirq.json", "random_connected_20q_dense.json")
    receipts = []
    for name in names:
        path = folder / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        identity = payload.get("results", payload)
        if payload.get("status") != "PASS":
            raise RuntimeError(f"historical reference receipt is not PASS: {name}")
        if identity.get("source_sha256") != source_hash:
            raise RuntimeError(f"historical reference source identity differs: {name}")
        if (identity.get("gate_sequence_sha256") != gate_hash
                or identity.get("gates", identity.get("gate_count")) != gate_count):
            raise RuntimeError(f"historical reference circuit identity differs: {name}")
        receipts.append({"path": path.relative_to(ROOT).as_posix(),
                         "sha256": sha256(path.read_bytes()),
                         "kind": name.removeprefix("random_connected_20q_").removesuffix(".json")})
    comparison = json.loads((folder / names[0]).read_text(encoding="utf-8"))
    if not comparison.get("checks", {}).get("all_checks_pass"):
        raise RuntimeError("stored Qiskit/Cirq/dense/sparse comparison is not fully passing")
    return {"method": "prior independent complete Qiskit and Cirq statevector comparisons;"
                       " adaptive is compared componentwise against the same dense candidate",
            "checks_all_pass": True, "receipts": receipts}


def _orchestrate(args):
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    with tempfile.TemporaryDirectory(prefix="sharkbyte-adaptive-") as temp:
        temp_path = Path(temp)
        for case in (args.only_case,) if args.only_case else CASES:
            source = _source_for_case(case)
            source_path = temp_path / f"{case}.sbq"
            source_path.write_bytes(source)
            circuit, parsed_hash = load_circuit(source_path)
            case_results = {}
            for backend in BACKENDS:
                report_path = temp_path / f"{case}-{backend}.json"
                vector_path = report_path.with_suffix(".npy")
                started = time.perf_counter()
                completed = subprocess.run(
                    [sys.executable, "-B", str(Path(__file__).resolve()), "--worker",
                     "--case", case, "--backend", backend, "--source", str(source_path),
                     "--output", str(report_path), "--warmups", str(args.warmups),
                     "--repetitions", str(args.repetitions)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=args.timeout_seconds)
                startup_and_worker_seconds = time.perf_counter() - started
                if completed.returncode:
                    raise RuntimeError(f"{case}/{backend} worker failed ({completed.returncode}):\n"
                                       f"{completed.stdout}\n{completed.stderr}")
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["worker_process_total_seconds_including_startup"] = startup_and_worker_seconds
                case_results[backend] = report
            reference = np.load(temp_path / f"{case}-dense.npy", allow_pickle=False, mmap_mode="r")
            for backend in BACKENDS:
                vector = np.load(temp_path / f"{case}-{backend}.npy", allow_pickle=False, mmap_mode="r")
                if vector.shape != reference.shape:
                    raise RuntimeError(f"{case}/{backend}: statevector length mismatch")
                max_error = float(np.max(np.abs(vector - reference)))
                case_results[backend]["maximum_complex_amplitude_error_vs_dense"] = max_error
                case_results[backend]["agrees_with_dense_candidate"] = max_error <= 2e-12
                if not case_results[backend]["agrees_with_dense_candidate"]:
                    raise RuntimeError(f"{case}/{backend}: maximum amplitude error {max_error} exceeds 2e-12")
                if not math.isclose(case_results[backend]["normalization"], 1.0,
                                    rel_tol=0.0, abs_tol=1e-10):
                    raise RuntimeError(f"{case}/{backend}: normalization is outside tolerance")
                del vector
            del reference
            gc.collect()
            support = case_results["adaptive"]["active_amplitudes_exact_nonzero"]
            if case == "sparse_ghz_20q" and support != 2:
                raise RuntimeError(f"GHZ analytic support expected 2, got {support}")
            if case == "intermediate_20q" and support != 1 << 10:
                raise RuntimeError(f"intermediate analytic support expected 1024, got {support}")
            if case == "random_connected_20q" and support != 1 << 20:
                raise RuntimeError(f"high-support workload expected full support, got {support}")
            if case in ("sparse_ghz_20q", "intermediate_20q"):
                vector = np.load(temp_path / f"{case}-adaptive.npy", allow_pickle=False, mmap_mode="r")
                target_probability = 1.0 / support
                active_probabilities = np.square(np.abs(vector[vector != 0.0j]))
                uniform_error = float(np.max(np.abs(active_probabilities - target_probability)))
                if uniform_error > target_probability * 1e-12:
                    raise RuntimeError(f"{case}: structured analytical probabilities do not match")
                del active_probabilities, vector
            else:
                uniform_error = None
            gate_hash = sha256(canonical_json(gate_descriptors(circuit.gates)))
            results[case] = {
                "source_sha256": parsed_hash,
                "qubits": circuit.qubits, "gate_count": len(circuit.gates),
                "gate_sequence": [list(g) for g in circuit.gates],
                "backends": case_results,
                "verification": {"status": "PASS", "full_statevector_componentwise_vs_dense": True,
                                 "exact_support_matches_expected": True,
                                 "normalization_within_1e-10": all(
                                     math.isclose(x["normalization"], 1.0, rel_tol=0.0, abs_tol=1e-10)
                                     for x in case_results.values()),
                                 "structured_uniform_probability_error": uniform_error},
                "independent_reference": _reference_receipts(
                    case, parsed_hash, gate_hash, len(circuit.gates)),
            }
    summary = {
        "schema": 1, "status": "PASS", "title": "Experimental adaptive sparse/dense comparison",
        "measurement_plan": {"warmups_per_backend_case": args.warmups,
                              "timed_repetitions_per_backend_case": args.repetitions,
                              "primary_statistic": "median", "timing_units": "seconds",
                              "memory": "per-worker process peak RSS; backend workers are isolated subprocesses",
                              "circuit_setup": "source bytes read and parsed, measured separately",
                              "evolution": "backend API call; adaptive also reports separately measured state initialization/evolution",
                              "pruning": "disabled; support counts exact nonzero complex amplitudes"},
        "environment": {"host": platform.platform(), "architecture": platform.machine(),
                        "processor": platform.processor(), "python": platform.python_version(),
                        "numpy": np.__version__},
        "cases": results,
    }
    raw = json.dumps(summary, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    path = output / "adaptive-sparse-dense-windows-arm64.json"
    path.write_bytes(raw)
    manifest = {"path": path.name, "bytes": len(raw), "sha256": sha256(raw),
                "source_sha256": {name: value["source_sha256"] for name, value in results.items()},
                "code_sha256": {name: sha256((ROOT / name).read_bytes()) for name in (
                    "tools/high_support/adaptive_statevector.py",
                    "tools/high_support/dense_statevector.py",
                    "tools/high_support/benchmark_adaptive.py",
                    "benchmarks/sb_quantum_benchmark/sparse_backend.py")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                            encoding="utf-8")
    print(json.dumps({"status": summary["status"], "output": str(path),
                      "sha256": manifest["sha256"],
                      "cases": {case: {backend: {
                          "median_api_call_seconds": report["median_api_call_seconds"],
                          "peak_rss_bytes": report["peak_rss_bytes_process_lifetime"],
                          "max_amplitude_error": report["maximum_complex_amplitude_error_vs_dense"]}
                          for backend, report in result["backends"].items()}
                          for case, result in results.items()}}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--only-case", choices=CASES,
                        help="run one corpus case instead of the complete comparison matrix")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "evidence" / "adaptive_sparse_dense" / "windows_arm64")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.warmups < 1 or not 7 <= args.repetitions <= 31:
        parser.error("use at least one warmup and 7..31 timed repetitions")
    if args.worker:
        if not args.case or not args.backend or not args.source or not args.output:
            parser.error("worker mode requires --case, --backend, --source, and --output")
        report = _worker(args)
        print(json.dumps({"status": report["status"], "case": args.case,
                          "backend": args.backend, "support": report["active_amplitudes_exact_nonzero"]}))
    else:
        _orchestrate(args)


if __name__ == "__main__":
    main()
