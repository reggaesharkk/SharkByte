"""Measure a backend in a fresh process and compare every amplitude to |0>."""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from run_backend import ROOT, execute, load_circuit, peak_rss_bytes
from frontier30 import simplify_inverses

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backend", choices=("sparse", "dense", "qiskit", "cirq"))
    parser.add_argument("--simplify", action="store_true")
    args = parser.parse_args()
    circuit, digest = load_circuit(ROOT / "examples/high_support/roundtrip_17q.sbq")
    started = time.perf_counter()
    if args.simplify:
        circuit, _ = simplify_inverses(circuit)
    state, details = execute(args.backend, circuit, circuit.gates)
    elapsed = time.perf_counter() - started
    state = state.copy()
    state[0] -= 1
    error = float(np.linalg.norm(state))
    print(json.dumps(dict(source_sha256=digest, backend=args.backend, simplified=args.simplify,
                          seconds=elapsed, peak_process_bytes=peak_rss_bytes(), l2_error=error,
                          details=details)))
    raise SystemExit(0 if error < 1e-12 else 1)
