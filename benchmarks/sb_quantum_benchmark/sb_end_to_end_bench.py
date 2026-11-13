import cmath
import hashlib
import json
from pathlib import Path
import re
import time
import tracemalloc

from quantum_frontend import parse
from sparse_backend import Circuit, ResourceLimitError, evolve

ROOT = Path(__file__).resolve().parent


def run(path, expected):
    start = time.perf_counter()
    tracemalloc.start()
    try:
        data = path.read_bytes()
        match = re.fullmatch(r"\s*quantum\s+[A-Za-z_]\w*\s*\{([^{}]*)\}\s*", data.decode())
        if match is None:
            raise ValueError("Expected one named quantum block")
        parsed = parse(match[1], max_qubits=40, sparse=True)
        gates = tuple((op, args[1], args[2], args[0]) if op == "cp" else (op, *args)
                      for op, args in parsed["gates"])
        try:
            state = evolve(Circuit(parsed["n"], gates), support_cap=4096, max_seconds=5)
        except ResourceLimitError as exc:
            if expected is not None or "expand support to 8192; cap is 4096" not in str(exc):
                raise
            state = None
        elapsed = time.perf_counter() - start
        peak_bytes = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    if (state is None) != (expected is None):
        raise RuntimeError(f"Unexpected outcome for {path.name}")
    row = dict(source=path.name, source_sha256=hashlib.sha256(data).hexdigest(),
               qubits=parsed["n"], gates=len(gates), seconds_with_tracing=elapsed,
               peak_python_bytes=peak_bytes)
    if state is None:
        return dict(row, result="REFUSED", requested_support=8192, support_cap=4096)
    error = max(abs(state.get(i, 0) - expected.get(i, 0)) for i in state.keys() | expected.keys())
    if error > 1e-12:
        raise RuntimeError(f"Amplitude mismatch for {path.name}: {error}")
    peak_support = max(len(evolve(Circuit(parsed["n"], gates[:i]), support_cap=4096, max_seconds=5))
                       for i in range(len(gates) + 1))
    return dict(row, result="PASS", peak_populated_states=peak_support, max_amplitude_error=error)


if __name__ == "__main__":
    phase = cmath.exp(1j * 1.0471975511965976)
    echo = {0: (1 + phase) / 2, 1: (1 - phase) / 2}
    rows = [run(ROOT / f"echo{n}.sb", echo) for n in (16, 30)]
    rows.append(run(ROOT / "branch12.sb", dict.fromkeys(range(4096), 1 / 64)))
    rows.append(run(ROOT / "branch13.sb", None))
    report = dict(results=rows, module_sha256={
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("quantum_frontend.py", "sparse_backend.py", "sb_end_to_end_bench.py")
    })
    report["record_sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()
    print(json.dumps(report, indent=2))
