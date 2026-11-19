"""Run small reproducible full-vector controls with numerical reference packages."""
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import time
import tracemalloc

import numpy as np
from run_backend import ROOT, execute
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit, evolve
from benchmarks.sb_quantum_benchmark.bounded_support import simulate
from benchmarks.sb_quantum_benchmark.verify_bounded import replay


def measure(fn):
    tracemalloc.start()
    start = time.perf_counter()
    try:
        result = fn()
        return result, dict(seconds=time.perf_counter()-start,
                            peak_python_bytes=tracemalloc.get_traced_memory()[1])
    finally:
        tracemalloc.stop()


def compare(name, gates, protected=()):
    circuit = Circuit(8, tuple(gates))
    limits = dict(support_cap=256, memory_budget_bytes=256*(512+1024+512))
    exact, baseline = measure(lambda: evolve(circuit, **limits))
    (state, cert), compacted = measure(lambda: simulate(circuit, "1e-4", protected=protected, **limits))
    if state != replay(circuit, cert):
        raise AssertionError("replay mismatch")
    vector = np.array([state.get(i, 0j) for i in range(256)])
    errors = {}
    for backend in ("dense", "qiskit", "cirq"):
        reference, _ = execute(backend, circuit, gates)
        errors[backend] = float(np.linalg.norm(vector-reference))
        # Separate measured reference roundoff allowance for these small controls.
        if not errors[backend] <= float(Fraction(cert["charged_l2"])) + 1e-13:
            raise AssertionError((backend, errors))
    return dict(case=name, gates=gates, certificate=cert, baseline=baseline, compacted=compacted,
                original_support=len(exact), final_support=len(state), errors=errors)


if __name__ == "__main__":
    tiny = [("ry", q, 1e-6) for q in range(8)]
    cases = [compare("small-product", tiny), compare("protected-branch", tiny, (1,)),
             compare("coherent-repetition", [("ry", 0, 6e-5)]*12),
             compare("uniform", [("h", q) for q in range(8)])]
    forward = [("h", q) for q in range(8)] + [("cp", 0, 7, 0.713), ("ry", 2, 0.417)]
    inverse = [("ry", 2, -0.417), ("cp", 0, 7, -0.713)] + [("h", q) for q in reversed(range(8))]
    cases.append(compare("interference-return", forward + inverse))
    files = ["benchmarks/sb_quantum_benchmark/" + s + ".py" for s in
             ("bounded_support", "sparse_backend", "verify_bounded")]
    files += ["tools/high_support/" + s + ".py" for s in
              ("check_bounded", "dense_statevector", "run_backend")]
    print(json.dumps(dict(cases=cases, versions={p: importlib.metadata.version(p) for p in
                     ("numpy", "qiskit", "cirq-core")}, implementation_sha256={
                     f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}), indent=2))
