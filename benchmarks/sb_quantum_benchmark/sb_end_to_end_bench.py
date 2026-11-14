import cmath
import hashlib
import json
from pathlib import Path
import time
import tracemalloc

from frontier30 import DEFAULT_CAP, load_circuit
from sparse_backend import EvolutionStats, ResourceLimitError, evolve

ROOT = Path(__file__).resolve().parent


def run(path, expected):
    start = time.perf_counter()
    tracemalloc.start()
    stats = EvolutionStats()
    try:
        circuit, source_digest = load_circuit(path)
        try:
            state = evolve(circuit, support_cap=DEFAULT_CAP, max_seconds=5, stats=stats)
        except ResourceLimitError as exc:
            if expected is not None or exc.requested_support != 8192 or exc.gate_index != 12:
                raise
            state = None
        elapsed = time.perf_counter() - start
        peak_bytes = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    if (state is None) != (expected is None):
        raise RuntimeError(f"Unexpected outcome for {path.name}")
    row = dict(source=path.name, source_sha256=source_digest,
               qubits=circuit.qubits, gates=len(circuit.gates), seconds_with_tracing=elapsed,
               peak_python_bytes=peak_bytes)
    if state is None:
        return dict(row, result="REFUSED", requested_support=8192, support_cap=4096)
    error = max(abs(state.get(i, 0) - expected.get(i, 0)) for i in state.keys() | expected.keys())
    if error > 1e-12:
        raise RuntimeError(f"Amplitude mismatch for {path.name}: {error}")
    return dict(row, result="PASS", peak_populated_states=stats.peak_support,
                peak_gate_index=stats.peak_gate_index, max_amplitude_error=error)


if __name__ == "__main__":
    phase = cmath.exp(1j * 1.0471975511965976)
    echo = {0: (1 + phase) / 2, 1: (1 - phase) / 2}
    rows = [run(ROOT / f"echo{n}.sb", echo) for n in (16, 30)]
    rows.append(run(ROOT / "branch12.sb", dict.fromkeys(range(4096), 1 / 64)))
    rows.append(run(ROOT / "branch13.sb", None))
    # Input (|5> - |37>) / sqrt(2). Final swaps use natural DFT order.
    qft_reference = {
        k: (cmath.exp(2j * cmath.pi * 5 * k / 64)
            - cmath.exp(2j * cmath.pi * 37 * k / 64)) / (128 ** 0.5)
        for k in range(64)
    }
    rows.append(run(ROOT / "qft6_in_30.sb", qft_reference))
    report = dict(results=rows, module_sha256={
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("quantum_frontend.py", "sparse_backend.py", "sb_end_to_end_bench.py", "frontier30.py")
    })
    report["record_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    print(json.dumps(report, indent=2))
