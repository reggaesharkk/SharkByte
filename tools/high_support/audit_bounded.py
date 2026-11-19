"""Seeded full-vector comparisons and isolated sparse scaling workers."""
import argparse
from fractions import Fraction
import hashlib
import json
import platform
import random
import sys
import time
import tracemalloc

import numpy as np
from run_backend import ROOT, execute, peak_rss_bytes
from benchmarks.sb_quantum_benchmark.bounded_support import simulate
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit, ResourceLimitError, evolve
from benchmarks.sb_quantum_benchmark.verify_bounded import replay


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def fuzz():
    rows = []
    for width in (2, 4, 7):
        for seed in range(4):
            rng = random.Random(seed + 100*width)
            gates = []
            for _ in range(5):
                for op in ("ry", "h", "rx", "cx", "cp", "x", "rz", "z"):
                    a, b = rng.sample(range(width), 2)
                    angle = rng.choice([1e-6, -1e-4, 0.31, -1.17])
                    if op == "cx":
                        gate = (op, a, b)
                    elif op == "cp":
                        gate = (op, a, b, angle)
                    elif op in ("rx", "ry", "rz"):
                        gate = (op, a, angle)
                    else:
                        gate = (op, a)
                    gates.append(gate)
            circuit = Circuit(width, tuple(gates))
            limits = dict(support_cap=2**width, memory_budget_bytes=4<<20)
            original = evolve(circuit, **limits)
            baseline = np.array([original.get(i, 0j) for i in range(2**width)])
            references = {b: execute(b, circuit, gates)[0] for b in ("dense","qiskit","cirq")}
            for budget in ("1e-8", "1e-3"):
                for interval in (1, 7):
                    state, cert = simulate(circuit, budget, interval=interval, **limits)
                    assert replay(circuit, cert) == state
                    vector = np.array([state.get(i, 0j) for i in range(2**width)])
                    charge = float(Fraction(cert["charged_l2"]))
                    distances = {}
                    for name, ref in references.items():
                        fp = float(np.linalg.norm(baseline-ref))
                        total = float(np.linalg.norm(vector-ref))
                        assert fp < 1e-13 and total <= charge + 1e-13
                        distances[name] = [fp, total]
                    delta = float(np.linalg.norm(vector-baseline))
                    assert delta <= charge + 1e-13
                    rows.append(dict(width=width,seed=seed,gates_sha256=digest(gates),
                                     budget=budget,interval=interval,charge=charge,
                                     events=len(cert["events"]),paired_delta=delta,errors=distances))
    return rows


def scale(width, mode, case):
    gates = tuple(("ry", i, 1e-6) if case=="product" else ("h", i) for i in range(width))
    circuit = Circuit(width, gates)
    cap = min(2**width, 8192)
    trajectory = []
    def observe(index, count, support):
        trajectory.append(support)
    limits = dict(support_cap=cap, memory_budget_bytes=16<<20,
                  max_seconds=30, progress_callback=observe)
    started = time.perf_counter()
    tracemalloc.start()
    result = dict(width=width, mode=mode, case=case, gates_sha256=digest(gates), support_cap=cap)
    try:
        if mode=="bounded":
            state, cert = simulate(circuit, "1e-4", **limits)
        else:
            state = evolve(circuit, **limits)
            cert = None
        result.update(final_support=len(state),status="PASS")
    except ResourceLimitError as exc:
        result.update(status="REFUSED", reason=str(exc))
        cert = None
    result.update(seconds=time.perf_counter()-started,peak_traced_bytes=tracemalloc.get_traced_memory()[1],
                  peak_process_bytes=peak_rss_bytes(),support=trajectory)
    tracemalloc.stop()
    result["certificate_bytes"] = len(json.dumps(cert).encode()) if cert else 0
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=3)
    args = parser.parse_args()
    if args.worker:
        w,m,c = args.worker
        print(json.dumps(scale(int(w),m,c)))
    else:
        import importlib.metadata
        import subprocess
        workers = []
        for w in (8,12,16,20):
            for c in ("product","flat"):
                for m in ("baseline","bounded"):
                    cmd = [sys.executable,__file__,"--worker",str(w),m,c]
                    workers.append(json.loads(subprocess.check_output(cmd,timeout=60)))
        paths = ["benchmarks/sb_quantum_benchmark/"+f+".py" for f in
                 ("bounded_support","verify_bounded","sparse_backend")]
        paths += ["tools/high_support/"+f+".py" for f in ("audit_bounded","run_backend","dense_statevector")]
        print(json.dumps(dict(platform=platform.platform(),python=sys.version,
                              versions={p:importlib.metadata.version(p) for p in ("numpy","qiskit","cirq-core")},
                              hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                              fuzz=fuzz(),scaling=workers),indent=2))
