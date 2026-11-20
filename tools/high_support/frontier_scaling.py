"""Resource-bounded, source-bound scaling experiments for SharkByte's sparse engines.

This opt-in research runner never provisions cloud resources. Each computation runs
in a separately limited worker; the parent publishes a receipt only after every
worker has exited successfully and the complete JSON receipt verifies locally.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
HIGH = ROOT / "tools" / "high_support"
for _path in (str(BENCH), str(HIGH)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from sparse_backend import Circuit, EvolutionStats, ResourceLimitError, evolve

FAMILIES = ("basis-walk", "connected-ghz", "growing-support", "interference",
            "uncomputation", "dense-no-benefit")
DEFAULT_WIDTHS = (12, 16, 20, 24, 28, 30)
DEFAULT_REPEATS = 3
DEFAULT_MEMORY_MIB = 1536
DEFAULT_WORKER_SECONDS = 90.0
DEFAULT_TOTAL_SECONDS = 1800.0
SPARSE_BYTES_PER_AMPLITUDE = 512
DENSE_PLANNING_BYTES_PER_BASIS = 96
WORKER_BASELINE_BYTES = 256 * 1024 * 1024
REFERENCE_TOLERANCE = 2e-10
SCHEMA = "sharkbyte-frontier-scaling-v1"


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                            allow_nan=False).encode("utf-8")).hexdigest()


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _state_hash(state):
    digest = hashlib.sha256()
    for basis in sorted(state):
        amplitude = state[basis]
        digest.update(f"{basis}:{amplitude.real.hex()}:{amplitude.imag.hex()}\n".encode("ascii"))
    return digest.hexdigest()


def _source_hashes():
    names = (
        "benchmarks/sb_quantum_benchmark/sparse_backend.py",
        "benchmarks/sb_quantum_benchmark/frontier30.py",
        "benchmarks/sb_quantum_benchmark/bounded_support.py",
        "benchmarks/sb_quantum_benchmark/certified_support.py",
        "tools/high_support/dense_statevector.py",
        "tools/high_support/adaptive_statevector.py",
        "tools/high_support/frontier_scaling.py",
        "tools/high_support/verify_frontier_scaling.py",
    )
    return {name: _file_hash(ROOT / name) for name in names if (ROOT / name).is_file()}


def _physical_memory():
    if os.name == "nt":
        class MEMORYSTATUSEX(C.Structure):
            _fields_ = [("dwLength", C.c_ulong), ("dwMemoryLoad", C.c_ulong),
                        ("ullTotalPhys", C.c_ulonglong), ("ullAvailPhys", C.c_ulonglong),
                        ("ullTotalPageFile", C.c_ulonglong), ("ullAvailPageFile", C.c_ulonglong),
                        ("ullTotalVirtual", C.c_ulonglong), ("ullAvailVirtual", C.c_ulonglong),
                        ("ullAvailExtendedVirtual", C.c_ulonglong)]
        status = MEMORYSTATUSEX()
        status.dwLength = C.sizeof(status)
        kernel = C.WinDLL("kernel32", use_last_error=True)
        fn = kernel.GlobalMemoryStatusEx
        fn.argtypes, fn.restype = [C.POINTER(MEMORYSTATUSEX)], C.c_int
        if not fn(C.byref(status)):
            raise OSError(C.get_last_error(), "GlobalMemoryStatusEx failed")
        return {"total_bytes": int(status.ullTotalPhys), "available_bytes": int(status.ullAvailPhys)}
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        total = page * os.sysconf("SC_PHYS_PAGES")
        available = page * os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, ValueError, OSError) as exc:
        raise RuntimeError("physical memory inventory unavailable; refusing to run") from exc
    return {"total_bytes": total, "available_bytes": available}


def _worker_peak_rss():
    """Return peak resident bytes from OS accounting, not Python allocation tracing."""
    if os.name == "nt":
        class PROCESS_MEMORY_COUNTERS_EX(C.Structure):
            _fields_ = [("cb", C.c_ulong), ("PageFaultCount", C.c_ulong),
                        ("PeakWorkingSetSize", C.c_size_t), ("WorkingSetSize", C.c_size_t),
                        ("QuotaPeakPagedPoolUsage", C.c_size_t), ("QuotaPagedPoolUsage", C.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", C.c_size_t), ("QuotaNonPagedPoolUsage", C.c_size_t),
                        ("PagefileUsage", C.c_size_t), ("PeakPagefileUsage", C.c_size_t),
                        ("PrivateUsage", C.c_size_t)]
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = C.sizeof(counters)
        psapi = C.WinDLL("psapi", use_last_error=True)
        fn = psapi.GetProcessMemoryInfo
        fn.argtypes = [C.c_void_p, C.POINTER(PROCESS_MEMORY_COUNTERS_EX), C.c_ulong]
        fn.restype = C.c_int
        kernel = C.WinDLL("kernel32", use_last_error=True)
        get_current = kernel.GetCurrentProcess
        get_current.argtypes, get_current.restype = [], C.c_void_p
        process = get_current()
        if not fn(process, C.byref(counters), counters.cb):
            raise OSError(C.get_last_error(), "GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize), "Windows PeakWorkingSetSize"
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, AttributeError) as exc:
        raise RuntimeError("OS peak-RSS accounting unavailable; refusing to report memory") from exc
    # Linux reports KiB; other supported POSIX systems may report bytes.
    scale = 1024 if sys.platform.startswith("linux") else 1
    return int(value * scale), "getrusage(RUSAGE_SELF).ru_maxrss"


def _process_cpu_seconds():
    """Read a sub-millisecond process CPU counter on Windows ARM64 and Linux."""
    if os.name == "nt":
        class FILETIME(C.Structure):
            _fields_ = [("dwLowDateTime", C.c_ulong), ("dwHighDateTime", C.c_ulong)]
        kernel = C.WinDLL("kernel32", use_last_error=True)
        get_current = kernel.GetCurrentProcess
        get_current.argtypes, get_current.restype = [], C.c_void_p
        get_times = kernel.GetProcessTimes
        get_times.argtypes = [C.c_void_p, C.POINTER(FILETIME), C.POINTER(FILETIME),
                              C.POINTER(FILETIME), C.POINTER(FILETIME)]
        get_times.restype = C.c_int
        created, exited, kernel_time, user_time = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not get_times(get_current(), C.byref(created), C.byref(exited),
                         C.byref(kernel_time), C.byref(user_time)):
            raise OSError(C.get_last_error(), "GetProcessTimes failed")
        def ticks(value):
            return (value.dwHighDateTime << 32) | value.dwLowDateTime
        return (ticks(kernel_time) + ticks(user_time)) / 10_000_000
    return time.process_time_ns() / 1_000_000_000


def _measure_operation(operation, *, minimum_cpu_seconds=0.05, max_iterations=2048):
    """Average identical deterministic executions until OS CPU accounting resolves them."""
    cpu_start, wall_start = _process_cpu_seconds(), time.perf_counter()
    result, iterations = None, 0
    while iterations < max_iterations:
        result = operation()
        iterations += 1
        if _process_cpu_seconds() - cpu_start >= minimum_cpu_seconds:
            break
    cpu_elapsed = _process_cpu_seconds() - cpu_start
    wall_elapsed = time.perf_counter() - wall_start
    return result, cpu_elapsed / iterations, wall_elapsed / iterations, iterations


def build_circuit(family: str, qubits: int, seed: int) -> Circuit:
    if family not in FAMILIES or type(qubits) is not int or not 2 <= qubits <= 30:
        raise ValueError("unknown family or width outside [2,30]")
    if family == "basis-walk":
        rng = random.Random(seed + qubits * 1009)
        gates = []
        for _ in range(64):
            op = rng.choice(("x", "z", "cx"))
            if op == "cx":
                gates.append((op, *rng.sample(range(qubits), 2)))
            else:
                gates.append((op, rng.randrange(qubits)))
    elif family == "connected-ghz":
        gates = [("h", 0)] + [("cx", q - 1, q) for q in range(1, qubits)]
    elif family == "growing-support":
        gates = [("h", q) for q in range(qubits)]
    elif family == "interference":
        gates = [("h", 0), ("z", 0), ("h", 0)]
        gates.extend(("cx", 0, q) for q in range(1, qubits))
    elif family == "uncomputation":
        forward = [("h", q) for q in range(qubits)]
        forward.append(("cp", 0, qubits - 1, 0.371))
        inverse = [("cp", 0, qubits - 1, -0.371)]
        inverse.extend(("h", q) for q in reversed(range(qubits)))
        gates = forward + inverse
    else:
        gates = [("h", q) for q in range(qubits)]
        gates.extend(("z", q) for q in range(qubits))
    return Circuit(qubits, tuple(gates), f"frontier-{family}-{qubits}q-seed{seed}")


def estimated_peak(family: str, qubits: int, reference_qubits: int = 12):
    support = {"basis-walk": 1, "connected-ghz": 2, "growing-support": 1 << qubits,
               "interference": 2, "uncomputation": 1 << qubits,
               "dense-no-benefit": 1 << qubits}[family]
    sparse = support * SPARSE_BYTES_PER_AMPLITUDE
    # A full-vector reference is only requested at small widths, but include its
    # conservative planning estimate whenever the runner may ask for one.
    dense = ((1 << qubits) * DENSE_PLANNING_BYTES_PER_BASIS
             if qubits <= reference_qubits else 0)
    return {"peak_support_upper_bound": support, "sparse_planning_bytes": sparse,
            "dense_reference_planning_bytes": dense,
            "worker_baseline_reserve_bytes": WORKER_BASELINE_BYTES,
            "combined_planning_bytes": max(sparse, dense) + WORKER_BASELINE_BYTES}


def _analytic_check(family, qubits, circuit, state):
    inv = 1.0 / math.sqrt(2.0)
    if family == "basis-walk":
        basis, amplitude = 0, 1.0 + 0.0j
        for gate in circuit.gates:
            if gate[0] == "x":
                basis ^= 1 << gate[1]
            elif gate[0] == "cx" and basis & (1 << gate[1]):
                basis ^= 1 << gate[2]
            elif gate[0] == "z" and basis & (1 << gate[1]):
                amplitude = -amplitude
        expected = {basis: amplitude}
        error = max((abs(state.get(i, 0j) - value) for i, value in expected.items()), default=0.0)
        passed = state == expected
        reference = "independent signed-permutation coordinate replay"
    elif family == "connected-ghz":
        expected = {0: complex(inv), (1 << qubits) - 1: complex(inv)}
        error = max(abs(state.get(i, 0j) - v) for i, v in expected.items())
        passed = len(state) == 2 and all(state.get(i) == v for i, v in expected.items())
        reference = "closed-form GHZ amplitudes"
    elif family == "growing-support":
        amplitude = 1.0
        for _ in range(qubits):
            amplitude *= inv
        error = max((abs(value - amplitude) for value in state.values()), default=math.inf)
        passed = len(state) == (1 << qubits) and error == 0.0
        reference = "uniform Hadamard entry formula checked over every populated coordinate"
    elif family == "interference":
        low, high = inv, inv
        low, high = low, -high  # Z
        low, high = (low + high) * inv, (low - high) * inv  # H
        basis = (1 << qubits) - 1
        expected = {basis: complex(high)}
        error = abs(state.get(basis, 0j) - high)
        passed = len(state) == 1 and state.get(basis) == complex(high)
        reference = "independent two-amplitude interference calculation and CNOT coordinate map"
    elif family == "dense-no-benefit":
        amplitude = 1.0
        for _ in range(qubits):
            amplitude *= inv
        error = max((abs(value - (amplitude if basis.bit_count() % 2 == 0 else -amplitude))
                     for basis, value in state.items()), default=math.inf)
        passed = len(state) == (1 << qubits) and error == 0.0
        reference = "uniform signed Hadamard entry formula checked over every populated coordinate"
    else:
        # The exact ideal result follows algebraically from U followed by U^-1.
        norm = math.fsum(abs(value) ** 2 for value in state.values())
        error = math.sqrt(math.fsum(abs(value - (1.0 if basis == 0 else 0.0)) ** 2
                                     for basis, value in state.items())
                          + (1.0 if 0 not in state else 0.0))
        passed = math.isfinite(norm) and abs(norm - 1.0) <= 1e-10 and error <= 1e-10
        reference = "ideal inverse composition; floating execution residual measured separately"
    entries_checked = len(state) if family in ("growing-support", "dense-no-benefit") else len(expected) if family != "uncomputation" else len(state)
    return {"status": "PASS" if passed else "FAIL", "reference": reference,
            "reference_type": "analytic formula; no amplitudes analytically injected",
            "entries_checked": entries_checked, "max_or_l2_error": error}


def _full_reference_checks(circuit, state, requested, max_qubits):
    result = {}
    if circuit.qubits > max_qubits:
        return {name: {"status": "UNSUPPORTED", "reason": "full-vector reference width cap"}
                for name in requested}
    try:
        import numpy as np
        from dense_statevector import evolve as dense_evolve
        candidate, cpu_seconds, wall_seconds, iterations = _measure_operation(
            lambda: dense_evolve(circuit.qubits, circuit.gates))
        observed = np.zeros(1 << circuit.qubits, dtype=np.complex128)
        for basis, amplitude in state.items():
            observed[basis] = amplitude
        error = float(np.max(np.abs(candidate - observed)))
        result["numpy"] = {"status": "PASS" if error <= REFERENCE_TOLERANCE else "FAIL",
                            "basis_entries_compared": int(candidate.size),
                            "max_complex_amplitude_error": error,
                            "cpu_seconds": cpu_seconds, "wall_seconds": wall_seconds,
                            "measurement_iterations": iterations,
                            "reference_type": "complete dense complex128 statevector",
                            "backend": "independent dense NumPy complex128 implementation"}
    except (ImportError, MemoryError) as exc:
        result["numpy"] = {"status": "UNSUPPORTED", "reason": type(exc).__name__}
    for name in requested:
        if name == "numpy":
            continue
        if name == "qiskit":
            try:
                import qiskit  # load the package before the timed circuit build/evolution
                from sparse_backend import qiskit_statevector
                reference, cpu_seconds, wall_seconds, iterations = _measure_operation(
                    lambda: qiskit_statevector(circuit))
                import numpy as np
                observed = np.zeros(1 << circuit.qubits, dtype=np.complex128)
                for basis, amplitude in state.items():
                    observed[basis] = amplitude
                error = float(np.max(np.abs(reference - observed)))
                result[name] = {"status": "PASS" if error <= REFERENCE_TOLERANCE else "FAIL",
                                "basis_entries_compared": int(reference.size),
                                "max_complex_amplitude_error": error,
                                "cpu_seconds": cpu_seconds, "wall_seconds": wall_seconds,
                                "measurement_iterations": iterations,
                                "reference_type": "complete dense complex128 statevector",
                                "backend": f"Qiskit {getattr(qiskit, '__version__', 'unknown')}"}
            except (ImportError, MemoryError) as exc:
                result[name] = {"status": "UNSUPPORTED", "reason": type(exc).__name__}
        elif name == "cirq":
            try:
                import cirq
                import numpy as np
                def run_cirq():
                    qs = cirq.LineQubit.range(circuit.qubits)
                    operations = []
                    for gate in circuit.gates:
                        op, args = gate[0], gate[1:]
                        if op == "h": operations.append(cirq.H(qs[args[0]]))
                        elif op == "x": operations.append(cirq.X(qs[args[0]]))
                        elif op == "z": operations.append(cirq.Z(qs[args[0]]))
                        elif op == "cx": operations.append(cirq.CNOT(qs[args[0]], qs[args[1]]))
                        elif op == "cp": operations.append(cirq.CZPowGate(exponent=args[2] / math.pi)(qs[args[0]], qs[args[1]]))
                    return cirq.Simulator(dtype=np.complex128).simulate(
                        cirq.Circuit(operations), qubit_order=qs[::-1]).final_state_vector
                reference, cpu_seconds, wall_seconds, iterations = _measure_operation(run_cirq)
                observed = np.zeros(1 << circuit.qubits, dtype=np.complex128)
                for basis, amplitude in state.items():
                    observed[basis] = amplitude
                error = float(np.max(np.abs(reference - observed)))
                result[name] = {"status": "PASS" if error <= REFERENCE_TOLERANCE else "FAIL",
                                "basis_entries_compared": int(reference.size),
                                "max_complex_amplitude_error": error,
                                "cpu_seconds": cpu_seconds, "wall_seconds": wall_seconds,
                                "measurement_iterations": iterations,
                                "reference_type": "complete dense complex128 statevector",
                                "backend": f"Cirq {getattr(cirq, '__version__', 'unknown')}"}
            except (ImportError, MemoryError) as exc:
                result[name] = {"status": "UNSUPPORTED", "reason": type(exc).__name__}
    return result


def _run_case_worker(family, qubits, seed, repeats, reference_backends, reference_qubits):
    from frontier30 import simplify_inverses
    results = []
    for repeat in range(repeats):
        circuit = build_circuit(family, qubits, seed)
        (simplified, pairs), simplify_cpu, simplify_wall, simplify_iterations = _measure_operation(
            lambda: simplify_inverses(circuit))
        case_plan = estimated_peak(family, qubits)
        support_cap = max(1, case_plan["peak_support_upper_bound"])
        sparse_budget = max(SPARSE_BYTES_PER_AMPLITUDE, case_plan["sparse_planning_bytes"])
        def run_sparse_once():
            stats = EvolutionStats()
            trajectory = []
            state = evolve(circuit, support_cap=support_cap, memory_budget_bytes=sparse_budget,
                           max_seconds=DEFAULT_WORKER_SECONDS, stats=stats,
                           progress_callback=lambda done, total, active: trajectory.append([done, active]))
            return state, stats, trajectory
        (state, stats, trajectory), evolve_cpu, evolve_wall, evolve_iterations = _measure_operation(run_sparse_once)
        analytic = _analytic_check(family, qubits, circuit, state)
        optimized = None
        if len(simplified.gates) < len(circuit.gates):
            def run_optimized_once():
                optimized_stats = EvolutionStats()
                optimized_state = evolve(simplified, support_cap=support_cap,
                                         memory_budget_bytes=sparse_budget,
                                         max_seconds=DEFAULT_WORKER_SECONDS, stats=optimized_stats)
                return optimized_state, optimized_stats
            (optimized_state, optimized_stats), opt_cpu, opt_wall, opt_iterations = _measure_operation(run_optimized_once)
            optimized = {"executed_gates": len(simplified.gates), "state_sha256": _state_hash(optimized_state),
                         "final_support": len(optimized_state),
                         "peak_support": optimized_stats.peak_support,
                         "cpu_seconds": opt_cpu, "wall_seconds": opt_wall,
                         "measurement_iterations": opt_iterations,
                         "ideal_state_error": math.sqrt(math.fsum(abs(v - (1.0 if b == 0 else 0.0)) ** 2
                                                                  for b, v in optimized_state.items())
                                                       + (1.0 if 0 not in optimized_state else 0.0))}
        references = _full_reference_checks(circuit, state, reference_backends, reference_qubits)
        adaptive = None
        if family == "dense-no-benefit":
            try:
                from adaptive_statevector import AdaptiveStats, evolve_adaptive, to_dense
                def run_adaptive_once():
                    adaptive_stats = AdaptiveStats()
                    adaptive_state = evolve_adaptive(
                        circuit, support_cap=1 << qubits,
                        memory_budget_bytes=max(WORKER_BASELINE_BYTES, sparse_budget),
                        max_seconds=DEFAULT_WORKER_SECONDS, stats=adaptive_stats)
                    return adaptive_state, adaptive_stats
                (adaptive_state, adaptive_stats), adaptive_cpu, adaptive_wall, adaptive_iterations = _measure_operation(run_adaptive_once)
                import numpy as np
                adaptive_dense = to_dense(adaptive_state, qubits)
                sparse_dense = np.zeros(1 << qubits, dtype=np.complex128)
                for basis, amplitude in state.items(): sparse_dense[basis] = amplitude
                adaptive = {"status": "PASS" if np.max(np.abs(adaptive_dense-sparse_dense)) <= REFERENCE_TOLERANCE else "FAIL",
                            "representation": adaptive_stats.representation,
                            "transitions": adaptive_stats.transitions,
                            "cpu_seconds": adaptive_cpu, "wall_seconds": adaptive_wall,
                            "measurement_iterations": adaptive_iterations,
                            "max_complex_amplitude_error": float(np.max(np.abs(adaptive_dense-sparse_dense)))}
            except (ImportError, MemoryError, ResourceLimitError) as exc:
                adaptive = {"status": "UNSUPPORTED", "reason": type(exc).__name__}
        rss, rss_method = _worker_peak_rss()
        results.append({"repeat": repeat, "primary_representation": "sparse basis-to-amplitude dictionary",
                        "full_statevector_materialized_by_primary_engine": False,
                        "analytically_generated_state_entries": 0,
                        "state_dimension": 1 << qubits,
                        "state_sha256": _state_hash(state),
                        "sparse_state_entries": ([[basis, value.real.hex(), value.imag.hex()]
                                                  for basis, value in sorted(state.items())]
                                                 if len(state) <= 4096 else None),
                        "final_support": len(state), "peak_support": stats.peak_support,
                        "peak_gate_index_zero_based": stats.peak_gate_index,
                        "support_trajectory_gate_index_one_based": trajectory,
                        "probability_sum": math.fsum(abs(v) ** 2 for v in state.values()),
                        "evolution_cpu_seconds": evolve_cpu, "evolution_wall_seconds": evolve_wall,
                        "evolution_measurement_iterations": evolve_iterations,
                        "simplifier_cpu_seconds": simplify_cpu, "simplifier_wall_seconds": simplify_wall,
                        "simplifier_measurement_iterations": simplify_iterations,
                        "source_gate_count": len(circuit.gates),
                        "simplified_gate_count": len(simplified.gates),
                        "gates": [list(gate) for gate in circuit.gates],
                        "simplified_gates": [list(gate) for gate in simplified.gates],
                        "circuit_sha256": _json_hash({"qubits": qubits,
                                                      "gates": [list(gate) for gate in circuit.gates]}),
                        "cancellation_pairs_zero_based": pairs,
                        "optimized": optimized, "analytic_check": analytic,
                        "independent_references": references, "adaptive": adaptive,
                        "peak_resident_bytes": rss, "peak_resident_method": rss_method})
    summary = {
        "median_sparse_cpu_seconds": statistics.median(x["evolution_cpu_seconds"] for x in results),
        "median_sparse_wall_seconds": statistics.median(x["evolution_wall_seconds"] for x in results),
        "median_simplifier_cpu_seconds": statistics.median(x["simplifier_cpu_seconds"] for x in results),
        "median_simplifier_wall_seconds": statistics.median(x["simplifier_wall_seconds"] for x in results),
        "peak_resident_bytes_max_over_repeats": max(x["peak_resident_bytes"] for x in results),
        "final_support": results[0]["final_support"],
        "peak_support": max(x["peak_support"] for x in results),
    }
    optimized_rows = [x["optimized"] for x in results if x["optimized"] is not None]
    if optimized_rows:
        optimized_wall = statistics.median(x["wall_seconds"] for x in optimized_rows)
        summary["median_simplified_wall_seconds"] = optimized_wall
        summary["median_simplified_cpu_seconds"] = statistics.median(x["cpu_seconds"] for x in optimized_rows)
        summary["sparse_to_simplified_wall_ratio"] = (summary["median_sparse_wall_seconds"] / optimized_wall
                                                       if optimized_wall else None)
    adaptive_rows = [x["adaptive"] for x in results if x["adaptive"] and x["adaptive"].get("status") == "PASS"]
    if adaptive_rows:
        adaptive_wall = statistics.median(x["wall_seconds"] for x in adaptive_rows)
        summary["median_adaptive_wall_seconds"] = adaptive_wall
        summary["median_adaptive_cpu_seconds"] = statistics.median(x["cpu_seconds"] for x in adaptive_rows)
        summary["sparse_to_adaptive_wall_ratio"] = (summary["median_sparse_wall_seconds"] / adaptive_wall
                                                     if adaptive_wall else None)
    for backend in ("numpy", "qiskit", "cirq"):
        rows = [x["independent_references"][backend] for x in results
                if backend in x["independent_references"]
                and x["independent_references"][backend]["status"] == "PASS"]
        if rows:
            summary[f"median_{backend}_wall_seconds"] = statistics.median(x["wall_seconds"] for x in rows)
            summary[f"median_{backend}_cpu_seconds"] = statistics.median(x["cpu_seconds"] for x in rows)
    return {"family": family, "qubits": qubits, "seed": seed,
            "summary": summary, "repetitions": results}


def _compaction_case(kind):
    from benchmarks.sb_quantum_benchmark.certified_support import certify, verify
    qubits = 9
    if kind == "helpful":
        tiny = 1e-10
        initial = {0: complex(math.sqrt(1.0 - 255 * tiny * tiny), 0.0)}
        initial.update({basis: complex(tiny, 0.0) for basis in range(1, 256)})
        budget, gates, interval = "1/100000000", tuple(("x", q % qubits) for q in range(96)), 1
    else:
        initial = {basis: complex(1 / 16, 0.0) for basis in range(256)}
        budget, interval = "1/100000000", 16
        gates = tuple(("x", q % qubits) if q % 3 == 0 else
                      (("z", q % qubits) if q % 3 == 1 else ("cx", q % qubits, (q + 1) % qubits))
                      for q in range(96))
    circuit = Circuit(qubits, gates, f"compaction-{kind}")
    state_cap = len(initial)
    baseline, baseline_cpu, baseline_wall, baseline_iterations = _measure_operation(
        lambda: evolve(circuit, support_cap=state_cap,
                       memory_budget_bytes=state_cap * SPARSE_BYTES_PER_AMPLITUDE,
                       initial_state=initial, max_seconds=DEFAULT_WORKER_SECONDS))
    compacted, compact_cpu, compact_wall, compact_iterations = _measure_operation(
        lambda: certify(circuit, initial, budget, support_cap=state_cap,
                        memory_budget_bytes=state_cap * 4096,
                        max_seconds=DEFAULT_WORKER_SECONDS, interval=interval))
    if compacted.get("status") != "PASS":
        raise RuntimeError(f"compaction failed: {compacted}")
    cert = compacted["certificate"]
    certificate_bytes = len(json.dumps(cert, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    replay, _, replay_seconds, replay_iterations = _measure_operation(
        lambda: verify(circuit, initial, compacted["state"], cert, budget))
    if replay.get("status") != "PASS":
        raise RuntimeError(f"independent compaction replay failed: {replay}")
    peak_rss, rss_method = _worker_peak_rss()
    return {"family": f"compaction-{kind}", "qubits": qubits,
            "gates": [list(gate) for gate in gates],
            "initial_state": [[basis, value.real.hex(), value.imag.hex()]
                              for basis, value in sorted(initial.items())],
            "budget": budget, "interval": interval, "baseline_support": len(baseline),
            "compacted_support": len(compacted["state"]),
            "support_reduction": len(baseline)-len(compacted["state"]),
            "baseline_state_sha256": _state_hash(baseline),
            "compacted_state_sha256": _state_hash(compacted["state"]),
            "deletion_l2_bound": cert["error_components"]["total"],
            "certificate_bytes": certificate_bytes,
            "certificate_sha256": _json_hash(cert),
            "certificate": cert,
            "output_state": [[basis, value.real.hex(), value.imag.hex()]
                             for basis, value in sorted(compacted["state"].items())],
            "replay": replay, "replay_seconds": replay_seconds,
            "replay_measurement_iterations": replay_iterations,
            "baseline_cpu_seconds": baseline_cpu, "baseline_wall_seconds": baseline_wall,
            "baseline_measurement_iterations": baseline_iterations,
            "compaction_cpu_seconds": compact_cpu, "compaction_wall_seconds": compact_wall,
            "compaction_measurement_iterations": compact_iterations,
            "peak_resident_bytes": peak_rss,
            "peak_resident_method": rss_method}


def _worker(args):
    if args.worker_compaction:
        payload = _compaction_case(args.worker_compaction)
    else:
        payload = _run_case_worker(args.worker_family, args.worker_qubits, args.seed,
                                   args.repeats, args.reference_backends.split(",") if args.reference_backends else (),
                                   args.reference_qubits)
    path = Path(args.worker_output)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False),
                    encoding="utf-8", newline="\n")


def _set_linux_address_limit(limit_bytes):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("this process supervisor supports only native Windows and Linux")
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))


def _run_worker(command, deadline, memory_bytes, diagnostic_path):
    started = time.monotonic()
    system = platform.system()
    if system == "Windows":
        from windows_job import Job
        job = Job(memory_bytes)
        stage = {"phase": "frontier-scaling-worker"}
        report = {}
        try:
            job.run(command[1:], ROOT, deadline, stage)
        finally:
            job.finish(report)
        return {"elapsed_wall_seconds": time.monotonic()-started,
                "peak_job_committed_bytes": report.get("peak_job_committed_bytes"),
                "active_after_cleanup": report.get("active_after_cleanup", 0),
                "exit_status": stage.get("exit_status"), "containment": "Windows Job Object commit cap + kill-on-close"}
    if system == "Linux":
        remaining = max(0.0, deadline-time.monotonic())
        with open(diagnostic_path, "wb") as diagnostics:
            try:
                process = subprocess.Popen(command, cwd=ROOT, stdout=diagnostics,
                                           stderr=diagnostics,
                                           preexec_fn=lambda: _set_linux_address_limit(memory_bytes))
                try:
                    status = process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                    raise TimeoutError("external worker deadline expired")
            except OSError as exc:
                raise RuntimeError(f"contained worker could not launch: {exc}") from exc
        if status:
            raise ChildProcessError(status)
        return {"elapsed_wall_seconds": time.monotonic()-started,
                "exit_status": status, "containment": "RLIMIT_AS address-space cap + parent timeout"}
    raise RuntimeError(f"no supported fail-closed process containment for {system}")


def run(args):
    memory = _physical_memory()
    memory_limit = args.memory_mib * 1024 * 1024
    reserve = max(1536 * 1024**2, memory["total_bytes"] // 10)
    if memory_limit + reserve > memory["available_bytes"]:
        raise RuntimeError("configured worker budget plus 1.5-GiB/10% reserve exceeds current available physical memory")
    if args.repeats < 1 or args.repeats > 7 or args.memory_mib < 256:
        raise ValueError("repeats must be 1..7 and worker memory must be at least 256 MiB")
    if not math.isfinite(args.worker_seconds) or not 0 < args.worker_seconds <= 300:
        raise ValueError("per-worker timeout must be in (0,300] seconds")
    if not math.isfinite(args.max_total_seconds) or not 0 < args.max_total_seconds <= 7200:
        raise ValueError("total worker-time safeguard must be in (0,7200] seconds")
    if any(q < 12 or q > 30 for q in args.qubits):
        raise ValueError("scaling widths must be from 12 through 30")
    if len(set(args.qubits)) != len(args.qubits) or len(set(args.families)) != len(args.families):
        raise ValueError("duplicate widths or circuit families are not allowed")
    if type(args.reference_qubits) is not int or not 0 <= args.reference_qubits <= 20:
        raise ValueError("full-vector references are limited to 0..20 qubits by this runner")
    references = tuple(filter(None, args.reference_backends.split(",")))
    if len(set(references)) != len(references) or not set(references) <= {"numpy", "qiskit", "cirq"}:
        raise ValueError("reference backends must be a unique subset of numpy,qiskit,cirq")
    start = time.monotonic()
    deadline = start + args.max_total_seconds
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"schema": SCHEMA, "decision": "OPEN", "git_revision": _git_revision(),
              "configuration": {"qubits": args.qubits, "families": args.families,
                                "repeats": args.repeats, "seed": args.seed,
                                "worker_memory_limit_bytes": memory_limit,
                                "worker_timeout_seconds": args.worker_seconds,
                                "max_total_wall_seconds": args.max_total_seconds,
                                "full_reference_qubits": args.reference_qubits,
                                "requested_reference_backends": args.reference_backends.split(",") if args.reference_backends else [],
                                "cost_safeguard": "no cloud provisioning; hard total wall-time and per-worker caps"},
              "environment": {"platform": platform.platform(), "system": platform.system(),
                              "machine": platform.machine(), "python": sys.version,
                              "cpu_count": os.cpu_count(), "physical_memory": memory,
                              "worker_rss_metric": "OS peak resident working set/RSS, distinct from Python allocations and job commit"},
              "source_sha256": _source_hashes(), "cases": []}
    with tempfile.TemporaryDirectory(prefix="sharkbyte-frontier-") as temp:
        temp_path = Path(temp)
        for family in args.families:
            for qubits in args.qubits:
                plan = estimated_peak(family, qubits, args.reference_qubits)
                row = {"family": family, "qubits": qubits, "resource_plan": plan}
                if plan["combined_planning_bytes"] > memory_limit:
                    row.update(status="UNSUPPORTED", reason="pre-run memory plan exceeds worker cap; no allocation attempted")
                    report["cases"].append(row)
                    continue
                if time.monotonic() >= deadline:
                    row.update(status="UNSUPPORTED", reason="total runtime safeguard reached before worker launch")
                    report["cases"].append(row)
                    continue
                payload_path = temp_path / f"{family}-{qubits}.json"
                diag_path = temp_path / f"{family}-{qubits}.diagnostics.txt"
                command = [sys.executable, "-B", "-m", "tools.high_support.frontier_scaling",
                           "--worker-output", str(payload_path), "--worker-family", family,
                           "--worker-qubits", str(qubits), "--seed", str(args.seed),
                           "--repeats", str(args.repeats), "--reference-qubits", str(args.reference_qubits),
                           "--reference-backends", args.reference_backends]
                case_deadline = min(deadline, time.monotonic()+args.worker_seconds)
                try:
                    containment = _run_worker(command, case_deadline, memory_limit, diag_path)
                    if time.monotonic() >= case_deadline:
                        raise TimeoutError("worker deadline expired during output parsing")
                    parse_started = time.perf_counter()
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                    payload_parse_seconds = time.perf_counter()-parse_started
                    if time.monotonic() >= case_deadline:
                        raise TimeoutError("worker deadline expired after output parsing")
                    row.update(status="PASS", payload=payload, supervisor=containment,
                               payload_parse_seconds=payload_parse_seconds)
                    if any(rep["analytic_check"]["status"] != "PASS" for rep in payload["repetitions"]):
                        row["status"] = "FAIL"
                    for rep in payload["repetitions"]:
                        for ref in rep["independent_references"].values():
                            if ref["status"] == "FAIL":
                                row["status"] = "FAIL"
                except TimeoutError as exc:
                    diag_path.write_text(repr(exc), encoding="utf-8")
                    row.update(status="FAIL", reason=str(exc), diagnostics=diag_path.read_text(errors="replace") if diag_path.exists() else "")
                except (ChildProcessError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
                    if not diag_path.exists():
                        diag_path.write_text(repr(exc), encoding="utf-8")
                    row.update(status="FAIL", reason=repr(exc), diagnostics=diag_path.read_text(errors="replace") if diag_path.exists() else "")
                report["cases"].append(row)
                if time.monotonic() >= deadline:
                    break
            if time.monotonic() >= deadline:
                break
        if args.include_compaction and time.monotonic() < deadline:
            for kind in ("helpful", "no-benefit"):
                plan = {"peak_support_upper_bound": 256,
                        "sparse_planning_bytes": 256 * SPARSE_BYTES_PER_AMPLITUDE,
                        "worker_baseline_reserve_bytes": WORKER_BASELINE_BYTES}
                plan["combined_planning_bytes"] = (plan["sparse_planning_bytes"]
                                                    + plan["worker_baseline_reserve_bytes"])
                row = {"family": f"compaction-{kind}", "qubits": 9, "resource_plan": plan}
                if plan["combined_planning_bytes"] > memory_limit:
                    row.update(status="UNSUPPORTED", reason="pre-run compaction plan exceeds worker cap; no allocation attempted")
                    report["cases"].append(row)
                    continue
                payload_path = temp_path / f"compaction-{kind}.json"
                diag_path = temp_path / f"compaction-{kind}.diagnostics.txt"
                command = [sys.executable, "-B", "-m", "tools.high_support.frontier_scaling",
                           "--worker-output", str(payload_path), "--worker-compaction", kind,
                           "--seed", str(args.seed), "--repeats", "1", "--reference-qubits", "0",
                           "--reference-backends", ""]
                case_deadline = min(deadline, time.monotonic()+args.worker_seconds)
                try:
                    containment = _run_worker(command, case_deadline, memory_limit, diag_path)
                    if time.monotonic() >= case_deadline:
                        raise TimeoutError("compaction worker deadline expired during output parsing")
                    parse_started = time.perf_counter()
                    payload = json.loads(payload_path.read_text(encoding="utf-8"))
                    payload_parse_seconds = time.perf_counter()-parse_started
                    if time.monotonic() >= case_deadline:
                        raise TimeoutError("compaction worker deadline expired after output parsing")
                    row.update(status="PASS", payload=payload, supervisor=containment,
                               payload_parse_seconds=payload_parse_seconds)
                except (TimeoutError, ChildProcessError, OSError, RuntimeError, ValueError,
                        json.JSONDecodeError) as exc:
                    if not diag_path.exists():
                        diag_path.write_text(repr(exc), encoding="utf-8")
                    row.update(status="FAIL", reason=repr(exc), diagnostics=diag_path.read_text(errors="replace") if diag_path.exists() else "")
                report["cases"].append(row)
    report["elapsed_before_receipt_publication_seconds"] = time.monotonic()-start
    statuses = [row["status"] for row in report["cases"]]
    report["decision"] = "FAIL" if "FAIL" in statuses else ("PASS" if statuses and all(s in ("PASS", "UNSUPPORTED") for s in statuses) else "OPEN")
    report["record_sha256"] = _json_hash(report)
    payload = json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+"\n"
    if time.monotonic() >= deadline:
        raise TimeoutError("run-wide deadline expired before receipt publication")
    _atomic_publish(output, payload, deadline=deadline)
    return report


def _atomic_publish(output, payload, *, deadline=float("inf")):
    if output.exists():
        raise FileExistsError(output)
    temp = output.with_name(output.name + f".{os.getpid()}.partial")
    if temp.exists():
        raise FileExistsError(temp)
    try:
        with open(temp, "x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if time.monotonic() >= deadline:
            raise TimeoutError("deadline expired before atomic receipt publication")
        created_stat = temp.stat()
        if os.name == "nt":
            os.rename(temp, output)  # Windows rename refuses to replace an existing destination
        else:
            os.link(temp, output)  # atomic, same-filesystem, and fails if the destination exists
            temp.unlink()
        if time.monotonic() >= deadline:
            if output.exists() and os.path.samestat(output.stat(), created_stat):
                output.unlink()
            raise TimeoutError("deadline expired during atomic receipt publication")
    finally:
        if temp.exists():
            temp.unlink()


def _git_revision():
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                       text=True, timeout=5).strip()
    except Exception:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--qubits", type=int, nargs="+", default=DEFAULT_WIDTHS)
    parser.add_argument("--families", choices=FAMILIES, nargs="+", default=FAMILIES)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=20261120)
    parser.add_argument("--memory-mib", type=int, default=DEFAULT_MEMORY_MIB,
                        help="hard per-worker commit/address-space cap")
    parser.add_argument("--worker-seconds", type=float, default=DEFAULT_WORKER_SECONDS)
    parser.add_argument("--max-total-seconds", type=float, default=DEFAULT_TOTAL_SECONDS,
                        help="hard run-wide wall-time safeguard; no cloud VM is provisioned")
    parser.add_argument("--reference-qubits", type=int, default=12)
    parser.add_argument("--reference-backends", default="numpy,qiskit,cirq")
    parser.add_argument("--include-compaction", action="store_true")
    parser.add_argument("--worker-output", help=argparse.SUPPRESS)
    parser.add_argument("--worker-family", choices=FAMILIES, help=argparse.SUPPRESS)
    parser.add_argument("--worker-qubits", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker-compaction", choices=("helpful", "no-benefit"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker_output:
        _worker(args)
        return 0
    if args.output is None:
        parser.error("--output is required")
    try:
        report = run(args)
    except (OSError, RuntimeError, ValueError, ResourceLimitError) as exc:
        parser.error(str(exc))
    print(json.dumps({"decision": report["decision"], "record_sha256": report["record_sha256"],
                      "output": str(args.output.resolve())}, sort_keys=True))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
