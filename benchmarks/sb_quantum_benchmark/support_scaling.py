"""Measure sparse evolution above the Studio cap without printing every amplitude."""

import argparse
import json
import math
from pathlib import Path
from time import perf_counter

from frontier30 import load_circuit
from sparse_backend import Circuit, ESTIMATED_BYTES_PER_AMPLITUDE, EvolutionStats, evolve


def build_circuit(states):
    """Return the exact historical support-scaling circuit for a state cap."""
    if type(states) is not int or states not in tuple(1 << bits for bits in range(17, 25)):
        raise ValueError("states must be a power of two from 131,072 through 16,777,216")
    source = Path(__file__).resolve().parents[2] / "examples" / "frontier_sparse_40_131072.sb"
    base, source_hash = load_circuit(source)
    added = tuple(("h", q) for q in (14, 16, 18, 20, 22, 2, 6)[: states.bit_length() - 18])
    return Circuit(base.qubits, base.gates + added, "support_scaling"), source_hash, added, source


def run_scaling(states, *, progress_callback=None, stage_callback=None):
    """Execute and analytically check a historical sparse scaling workload."""
    if stage_callback:
        stage_callback("loading", 0, 0, 1)
    circuit, source_hash, added, _ = build_circuit(states)
    budget = states * ESTIMATED_BYTES_PER_AMPLITUDE
    stats = EvolutionStats()
    if stage_callback:
        stage_callback("evolving", 0, len(circuit.gates), 1)
    started = perf_counter()
    state = evolve(circuit, support_cap=states, memory_budget_bytes=budget,
                   max_seconds=60 if states >= 8388608 else 20, stats=stats,
                   progress_callback=progress_callback)
    evolution_seconds = perf_counter() - started
    if stage_callback:
        stage_callback("validating", len(circuit.gates), len(circuit.gates), len(state))
    expected = 1 / states
    total = math.fsum(abs(amplitude)**2 for amplitude in state.values())
    max_error = max(abs(abs(amplitude)**2 - expected) for amplitude in state.values())
    passed = (len(state) == stats.peak_support == states
              and abs(total - 1) <= 1e-12 and max_error <= expected * 1e-12)
    report = {"status": "PASS" if passed else "FAIL", "qubits": circuit.qubits,
              "gates": len(circuit.gates), "source_sha256": source_hash,
              "added_gates": added, "peak_active_states": stats.peak_support,
              "final_active_states": len(state), "estimated_budget_bytes": budget,
              "evolution_seconds": evolution_seconds, "probability_sum": total,
              "max_uniform_probability_error": max_error}
    if stage_callback:
        stage_callback("completed" if passed else "failed", len(circuit.gates),
                       len(circuit.gates), len(state))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("states", type=int, choices=tuple(1 << bits for bits in range(17, 25)))
    parser.add_argument("--progress-file", type=Path,
                        help="append JSON Lines phase and gate progress (used by Studio)")
    args = parser.parse_args()
    def progress(phase, gate_index, gate_count, active_states):
        if args.progress_file is None:
            return
        with args.progress_file.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps({"phase": phase, "gate_index": gate_index,
                                     "gate_count": gate_count,
                                     "active_states": active_states}) + "\n")
            stream.flush()
    report = run_scaling(args.states,
                         progress_callback=lambda done, total, active: progress(
                             "evolving", done, total, active),
                         stage_callback=lambda phase, done, total, active: progress(
                             phase, done, total, active))
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
