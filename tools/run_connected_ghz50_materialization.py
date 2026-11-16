"""Exhaustively materialize a connected 50-qubit GHZ-family state on disk.

This is a bounded, disk-backed closed-form amplitude experiment, not a general
purpose 50-qubit gate-by-gate simulator. It writes every active (basis,
complex128 amplitude) pair to temporary packed arrays, verifies every byte
against an independently implemented parity oracle, hashes both full arrays,
and removes the arrays after producing a compact receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
from frontier30 import load_circuit

QUBITS = 50
MAX_LOCAL_H = 31
GIB = 1024 ** 3
PARITY_TABLE = np.fromiter(
    (value.bit_count() & 1 for value in range(256)), dtype=np.uint8, count=256
)
CODE_PATHS = (
    "benchmarks/sb_quantum_benchmark/frontier30.py",
    "benchmarks/sb_quantum_benchmark/quantum_frontend.py",
    "benchmarks/sb_quantum_benchmark/sparse_backend.py",
    "tools/run_connected_ghz50_materialization.py",
)


class ResourceRefusal(RuntimeError):
    pass


def sha256_file(path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: dict) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def available_memory_bytes() -> int:
    try:
        rows = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
        available = int(next(row.split()[1] for row in rows
                             if row.startswith("MemAvailable:"))) * 1024
    except (OSError, StopIteration, ValueError):
        return 0
    for limit_path, usage_path in (
        (Path("/sys/fs/cgroup/memory.max"), Path("/sys/fs/cgroup/memory.current")),
        (Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
         Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")),
    ):
        try:
            limit_text = limit_path.read_text(encoding="utf-8").strip()
            if limit_text.isdecimal():
                available = min(available, max(0, int(limit_text)
                                                - int(usage_path.read_text())))
        except (OSError, ValueError):
            continue
    return available


def process_rss_bytes() -> int:
    try:
        rows = Path("/proc/self/status").read_text(encoding="utf-8").splitlines()
        return int(next(row.split()[1] for row in rows if row.startswith("VmRSS:"))) * 1024
    except (OSError, StopIteration, ValueError):
        return 0


def peak_rss_bytes() -> int:
    try:
        rows = Path("/proc/self/status").read_text(encoding="utf-8").splitlines()
        return int(next(row.split()[1] for row in rows if row.startswith("VmHWM:"))) * 1024
    except (OSError, StopIteration, ValueError):
        return process_rss_bytes()


def expected_gates(expanded: int) -> tuple[tuple, ...]:
    return (("h", 0),) + tuple(("cx", q, q + 1) for q in range(QUBITS - 1)) + tuple(
        ("h", q) for q in range(expanded)
    )


def validate_source(source: Path):
    raw = source.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    circuit, parsed_hash = load_circuit(source)
    expanded = len(circuit.gates) - QUBITS
    gates = expected_gates(expanded) if 0 <= expanded <= MAX_LOCAL_H else ()
    if (parsed_hash != source_hash or circuit.qubits != QUBITS
            or not gates or circuit.gates != gates):
        raise ValueError("Source does not match the frozen connected 50-qubit GHZ family")
    return circuit, source_hash, expanded, gates


def cirq_measurement_check(expanded: int, *, seed: int, repetitions: int) -> dict:
    qubits = cirq.LineQubit.range(QUBITS)
    circuit = cirq.Circuit()
    circuit.append(cirq.H(qubits[0]))
    circuit.append((cirq.CNOT(qubits[q], qubits[q + 1])
                    for q in range(QUBITS - 1)),
                   strategy=cirq.InsertStrategy.NEW)
    circuit.append((cirq.H(qubits[q]) for q in range(expanded)),
                   strategy=cirq.InsertStrategy.NEW)
    circuit.append(cirq.measure(*qubits, key="bits"),
                   strategy=cirq.InsertStrategy.NEW)
    started = time.perf_counter()
    samples = cirq.CliffordSimulator(seed=seed).run(
        circuit, repetitions=repetitions
    ).measurements["bits"]
    elapsed = time.perf_counter() - started
    tails = samples[:, expanded:]
    tail_equal = bool(np.all(tails == tails[:, :1]))
    branches = sorted({int(value) for value in tails[:, 0]})
    return {
        "status": "PASS" if tail_equal and branches == [0, 1] else "FAIL",
        "method": "independent Cirq CliffordSimulator measurement invariant",
        "repetitions": repetitions,
        "seed": seed,
        "unexpanded_tail_qubits": QUBITS - expanded,
        "all_tail_bits_correlated_per_shot": tail_equal,
        "observed_correlated_tail_branches": branches,
        "elapsed_seconds": elapsed,
    }


def folded_parity(values: np.ndarray) -> np.ndarray:
    parity = values.copy()
    for shift in (32, 16, 8, 4, 2, 1):
        parity ^= parity >> np.uint64(shift)
    return (parity & np.uint64(1)).astype(np.uint8, copy=False)


def table_parity(values: np.ndarray) -> np.ndarray:
    """Independent byte-table parity used by the full-vector verifier."""
    parity = np.zeros(values.size, dtype=np.uint8)
    for shift in range(0, 64, 8):
        byte_values = ((values >> np.uint64(shift)) & np.uint64(0xFF)).astype(np.uint8)
        parity ^= PARITY_TABLE[byte_values]
    return parity


def write_progress(path: Path | None, phase: str, done: int, total: int) -> None:
    if path is None:
        return
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"phase": phase, "items_done": done,
                                 "items_total": total}) + "\n")
        stream.flush()


def flush_and_drop_pages(array: np.memmap, path: Path, start: int, stop: int,
                         item_bytes: int, *, flush: bool) -> None:
    """Keep sequential file-backed work out of the worker's resident set."""
    byte_start = start * item_bytes
    byte_stop = stop * item_bytes
    if flush:
        array._mmap.flush(byte_start, byte_stop - byte_start)
    advice = getattr(mmap, "MADV_DONTNEED", None)
    if advice is not None and hasattr(array._mmap, "madvise"):
        array._mmap.madvise(advice, byte_start, byte_stop)
    if hasattr(os, "posix_fadvise") and hasattr(os, "POSIX_FADV_DONTNEED"):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(descriptor, byte_start, byte_stop - byte_start,
                             os.POSIX_FADV_DONTNEED)
        finally:
            os.close(descriptor)


def verify_receipt_fields(report: dict) -> None:
    report["receipt_sha256"] = canonical_sha256(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-dir", type=Path, required=True)
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--memory-budget-mib", type=int, default=4096)
    parser.add_argument("--minimum-free-disk-gib", type=int, default=10)
    parser.add_argument("--chunk-elements", type=int, default=1 << 22)
    parser.add_argument("--max-seconds", type=float, default=900.0)
    parser.add_argument("--cirq-seed", type=int, default=20261117)
    parser.add_argument("--cirq-repetitions", type=int, default=512)
    parser.add_argument("--notebook-sha256", default="")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    scratch = args.scratch_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Refusing to overwrite receipt: {output}")
    if (not 1 <= args.chunk_elements <= 1 << 22
            or ((args.chunk_elements * 8) % mmap.PAGESIZE) != 0
            or ((args.chunk_elements * 16) % mmap.PAGESIZE) != 0):
        parser.error("chunk-elements must be page-aligned and in [1, 4194304]")
    if args.memory_budget_mib < 512:
        parser.error("memory budget must be at least 512 MiB")

    circuit, source_hash, expanded, gates = validate_source(source)
    target_states = 1 << (expanded + 1)
    output_bytes = target_states * 24  # uint64 basis plus complex128 amplitude
    available_before = available_memory_bytes()
    free_disk = shutil.disk_usage(scratch).free
    disk_reserve = args.minimum_free_disk_gib * GIB
    memory_budget = args.memory_budget_mib * 1024 * 1024
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    code_hashes = {path: sha256_file(ROOT / path)
                   for path in (*CODE_PATHS, source.relative_to(ROOT).as_posix())}
    report_base = {
        "format": "sharkbyte-connected-ghz50-disk-materialization-v1",
        "source_commit": git_commit,
        "source_path": source.relative_to(ROOT).as_posix(),
        "source_sha256": source_hash,
        "notebook_sha256": args.notebook_sha256 or None,
        "circuit_identity": {
            "qubits": QUBITS,
            "gate_count": len(gates),
            "ordered_gates_sha256": canonical_sha256({"gates": gates}),
            "expanded_local_hadamards": expanded,
            "connected_cnot_chain_edges": QUBITS - 1,
        },
        "target_active_states": target_states,
        "packed_array_bytes": output_bytes,
        "packed_format": {"basis": "little-endian uint64", "amplitude": "little-endian complex128"},
        "environment": {
            "platform": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "cirq_core": cirq.__version__,
            "available_memory_before_bytes": available_before,
            "free_disk_before_bytes": free_disk,
            "memory_budget_bytes": memory_budget,
            "disk_reserve_bytes": disk_reserve,
            "chunk_elements": args.chunk_elements,
        },
        "code_sha256": code_hashes,
        "interpretation": {
            "method": "exhaustive disk-backed materialization and full-array verification from the closed-form GHZ/local-H amplitude equation",
            "not_a_general_gate_by_gate_simulation": True,
            "not_a_dense_50_qubit_statevector": True,
            "dense_complex128_statevector_bytes": (1 << QUBITS) * 16,
            "dense_size_human": "16 PiB",
            "claim_limit": "The amplitude table is a structured GHZ-family result. Cirq independently checks a Clifford measurement invariant; it does not independently compare every amplitude.",
        },
    }

    if free_disk < output_bytes + disk_reserve:
        report = {**report_base, "status": "REFUSED",
                  "resource_refusal": "Insufficient free disk for packed arrays plus configured reserve."}
        verify_receipt_fields(report)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": "REFUSED", "reason": report["resource_refusal"],
                          "required_bytes": output_bytes + disk_reserve,
                          "available_bytes": free_disk}))
        return 2
    if available_before < 2 * GIB:
        report = {**report_base, "status": "REFUSED",
                  "resource_refusal": "Less than 2 GiB available RAM before run."}
        verify_receipt_fields(report)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": "REFUSED", "reason": report["resource_refusal"]}))
        return 2

    basis_path = scratch / "connected-ghz50-basis.u64"
    amplitude_path = scratch / "connected-ghz50-amplitudes.c128"
    if basis_path.exists() or amplitude_path.exists():
        parser.error("Refusing to overwrite existing scratch arrays")
    deadline = time.monotonic() + args.max_seconds
    cirq_check = cirq_measurement_check(
        expanded, seed=args.cirq_seed, repetitions=args.cirq_repetitions
    )
    half = 1 << expanded
    tail_base = (1 << QUBITS) - half
    amplitude = 1.0 / math.sqrt(target_states)
    generation_start = time.perf_counter()
    progress_path = args.progress_file.resolve() if args.progress_file else None
    last_rss = 0
    basis_map = amplitude_map = None
    try:
        basis_map = np.memmap(basis_path, mode="w+", dtype="<u8", shape=(target_states,))
        amplitude_map = np.memmap(amplitude_path, mode="w+", dtype="<c16",
                                  shape=(target_states,))
        for branch, base in ((0, 0), (1, tail_base)):
            offset = branch * half
            for start in range(0, half, args.chunk_elements):
                if time.monotonic() >= deadline:
                    raise ResourceRefusal("wall-clock limit reached during materialization")
                stop = min(start + args.chunk_elements, half)
                indices = np.arange(start, stop, dtype=np.uint64)
                begin = offset + start
                end = offset + stop
                basis_map[begin:end] = indices + np.uint64(base)
                if branch == 0:
                    amplitude_map[begin:end] = amplitude
                else:
                    odd = folded_parity(indices).astype(bool, copy=False)
                    amplitude_map[begin:end] = np.where(odd, -amplitude, amplitude)
                flush_and_drop_pages(basis_map, basis_path, begin, end, 8, flush=True)
                flush_and_drop_pages(amplitude_map, amplitude_path, begin, end, 16,
                                     flush=True)
                last_rss = max(last_rss, process_rss_bytes())
                if last_rss > memory_budget:
                    raise ResourceRefusal("worker RSS crossed configured memory budget")
                write_progress(progress_path, "materialize", end, target_states)
                del indices
        generation_seconds = time.perf_counter() - generation_start

        verify_start = time.perf_counter()
        basis_hash = hashlib.sha256()
        amplitude_hash = hashlib.sha256()
        max_amplitude_error = 0.0
        max_probability_error = 0.0
        probability_parts = []
        compared = 0
        for branch, base in ((0, 0), (1, tail_base)):
            offset = branch * half
            for start in range(0, half, args.chunk_elements):
                if time.monotonic() >= deadline:
                    raise ResourceRefusal("wall-clock limit reached during verification")
                stop = min(start + args.chunk_elements, half)
                begin, end = offset + start, offset + stop
                indices = np.arange(start, stop, dtype=np.uint64)
                actual_basis = basis_map[begin:end]
                actual_amplitudes = amplitude_map[begin:end]
                if not np.array_equal(actual_basis, indices + np.uint64(base)):
                    raise ArithmeticError("basis-index formula mismatch")
                expected_amplitudes = np.full(stop - start, amplitude, dtype=np.complex128)
                if branch:
                    odd = table_parity(indices).astype(bool, copy=False)
                    expected_amplitudes[odd] = -amplitude
                amplitude_error = np.abs(actual_amplitudes - expected_amplitudes)
                if amplitude_error.size:
                    max_amplitude_error = max(max_amplitude_error,
                                              float(np.max(amplitude_error)))
                actual_probability = (actual_amplitudes.real * actual_amplitudes.real
                                      + actual_amplitudes.imag * actual_amplitudes.imag)
                expected_probability = 1.0 / target_states
                probability_error = np.abs(actual_probability - expected_probability)
                if probability_error.size:
                    max_probability_error = max(max_probability_error,
                                                float(np.max(probability_error)))
                probability_parts.append(float(np.sum(actual_probability, dtype=np.float64)))
                basis_hash.update(memoryview(actual_basis).cast("B"))
                amplitude_hash.update(memoryview(actual_amplitudes).cast("B"))
                flush_and_drop_pages(basis_map, basis_path, begin, end, 8,
                                     flush=False)
                flush_and_drop_pages(amplitude_map, amplitude_path, begin, end, 16,
                                     flush=False)
                compared += stop - start
                last_rss = max(last_rss, process_rss_bytes())
                if last_rss > memory_budget:
                    raise ResourceRefusal("worker RSS crossed configured memory budget")
                write_progress(progress_path, "verify", compared, target_states)
                del indices, actual_basis, actual_amplitudes, expected_amplitudes
        verification_seconds = time.perf_counter() - verify_start
        norm = math.fsum(probability_parts)
        basis_hash_hex = basis_hash.hexdigest()
        amplitude_hash_hex = amplitude_hash.hexdigest()
        arrays_ordered = True  # each chunk was compared to its strictly increasing formula
        passed = (compared == target_states and arrays_ordered
                  and max_amplitude_error <= 1e-15
                  and max_probability_error <= 1e-15
                  and abs(norm - 1.0) <= 2e-12
                  and cirq_check["status"] == "PASS")
        report = {
            **report_base,
            "status": "PASS" if passed else "FAIL",
            "full_array_check": {
                "status": "PASS" if passed else "FAIL",
                "basis_entries_compared": compared,
                "complex_amplitudes_compared": compared,
                "strictly_increasing_basis_proof": arrays_ordered,
                "all_expected_amplitudes_matched": max_amplitude_error == 0.0,
                "max_complex_amplitude_error": max_amplitude_error,
                "max_probability_error": max_probability_error,
                "probability_sum": norm,
                "tolerance": {"amplitude": 1e-15, "probability": 1e-15,
                              "normalization": 2e-12},
                "basis_array_sha256": basis_hash_hex,
                "amplitude_array_sha256": amplitude_hash_hex,
                "temporary_arrays_retained": False,
            },
            "entanglement_witness": {
                "status": "PASS",
                "state_construction": "H on q0 followed by a connected 49-edge CNOT chain, then local H gates on q0..q(expanded-1)",
                "all_nontrivial_bipartitions": {
                    "schmidt_rank": 2,
                    "schmidt_probabilities": [0.5, 0.5],
                    "entropy_bits": 1.0,
                    "reason": "The pre-local-unitary GHZ branches differ on every nonempty side of every proper bipartition; later gates are local unitaries and preserve Schmidt coefficients.",
                },
            },
            "cirq_reference": cirq_check,
            "timing_seconds": {
                "packed_disk_materialization": generation_seconds,
                "full_array_verification_and_hashing": verification_seconds,
                "total_before_receipt": time.perf_counter() - generation_start,
            },
            "memory_measurements": {
                "worker_sampled_peak_rss_bytes": last_rss,
                "worker_current_rss_at_receipt_bytes": process_rss_bytes(),
                "worker_high_water_rss_bytes": peak_rss_bytes(),
                "configured_budget_bytes": memory_budget,
            },
        }
        verify_receipt_fields(report)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": report["status"], "qubits": QUBITS,
                          "active_states": compared,
                          "max_amplitude_error": max_amplitude_error,
                          "probability_sum": norm,
                          "worker_peak_rss_bytes": last_rss,
                          "generation_seconds": generation_seconds,
                          "verification_seconds": verification_seconds}))
        print(f"Receipt: {output}")
        return 0 if passed else 1
    except ResourceRefusal as exc:
        report = {**report_base, "status": "RESOURCE_STOP",
                  "resource_stop_reason": str(exc),
                  "completed_items": compared if "compared" in locals() else 0,
                  "worker_peak_rss_bytes": max(last_rss, peak_rss_bytes())}
        verify_receipt_fields(report)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": report["status"], "reason": str(exc),
                          "completed_items": report["completed_items"]}))
        return 3
    finally:
        for array in (amplitude_map, basis_map):
            if array is not None:
                try:
                    array._mmap.close()
                except (OSError, ValueError):
                    pass
        for path in (basis_path, amplitude_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
