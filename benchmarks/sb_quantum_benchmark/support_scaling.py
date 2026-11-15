"""Measure sparse evolution above the Studio cap without printing every amplitude."""

import argparse
import json
import math
from pathlib import Path
from time import perf_counter

from frontier30 import load_circuit
from sparse_backend import Circuit, ESTIMATED_BYTES_PER_AMPLITUDE, EvolutionStats, evolve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", type=int, choices=(131072, 262144, 524288, 1048576, 2097152, 4194304))
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2] / "examples" / "frontier_sparse_40_131072.sb"
    base, source_hash = load_circuit(source)
    added = tuple(("h", q) for q in (14, 16, 18, 20, 22)[: args.states.bit_length() - 18])
    circuit = Circuit(base.qubits, base.gates + added, "support_scaling")
    budget = args.states * ESTIMATED_BYTES_PER_AMPLITUDE
    stats = EvolutionStats()
    started = perf_counter()
    state = evolve(circuit, support_cap=args.states, memory_budget_bytes=budget,
                   max_seconds=20, stats=stats)
    evolution_seconds = perf_counter() - started
    expected = 1 / args.states
    total = math.fsum(abs(amplitude)**2 for amplitude in state.values())
    max_error = max(abs(abs(amplitude)**2 - expected) for amplitude in state.values())
    passed = (len(state) == stats.peak_support == args.states
              and abs(total - 1) <= 1e-12 and max_error <= expected * 1e-12)
    print(json.dumps({"status": "PASS" if passed else "FAIL", "qubits": circuit.qubits,
                      "gates": len(circuit.gates), "source_sha256": source_hash,
                      "added_gates": added, "peak_active_states": stats.peak_support,
                      "final_active_states": len(state), "estimated_budget_bytes": budget,
                      "evolution_seconds": evolution_seconds, "probability_sum": total,
                      "max_uniform_probability_error": max_error}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
