"""Compare every populated state of the archived 40-qubit circuit with Cirq."""
import argparse
import hashlib
from importlib.metadata import version
from itertools import islice
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter

from run_cirq_crosscheck import cirq_state, np, ROOT, suite
from frontier30 import load_circuit
from sparse_backend import Circuit, EvolutionStats, evolve

BENCHMARK = ROOT / "benchmarks/sb_quantum_benchmark"
STATES = 1 << 24
TOLERANCE = 1e-12
REFERENCE_ZERO = 1e-14
BATCH = 1 << 16


def factorize(circuit):
    groups = [{q} for q in range(circuit.qubits)]
    for op, *args in circuit.gates:
        if op not in ("cx", "cp"):
            continue
        control, target = args[:2]
        left = next(group for group in groups if control in group)
        right = next(group for group in groups if target in group)
        if left is not right:
            left.update(right)
            groups.remove(right)

    for group in groups:
        indices = tuple(sorted(group))
        local = {q: i for i, q in enumerate(indices)}
        gates = []
        for op, *args in circuit.gates:
            if args[0] not in local:
                continue
            if op in ("cx", "cp"):
                gates.append((op, local[args[0]], local[args[1]], *args[2:]))
            else:
                gates.append((op, local[args[0]], *args[1:]))
        yield indices, cirq_state(len(indices), gates)


def compare(state, factors):
    peak_error = 0.0
    minimum_reference = math.inf
    entries = iter(state.items())
    while batch := list(islice(entries, BATCH)):
        basis = np.fromiter((key for key, _ in batch), dtype=np.uint64, count=len(batch))
        actual = np.fromiter((amp for _, amp in batch), dtype=np.complex128, count=len(batch))
        expected = np.ones(len(batch), dtype=np.complex128)
        for qubits, amplitudes in factors:
            local = np.zeros(len(batch), dtype=np.uint64)
            for index, q in enumerate(qubits):
                local |= ((basis >> q) & 1) << index
            expected *= amplitudes[local]
        peak_error = max(peak_error, float(np.max(np.abs(actual - expected))))
        minimum_reference = min(minimum_reference, float(np.min(np.abs(expected))))
    return peak_error, minimum_reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    archive = BENCHMARK / "scaling-16777216-ubuntu-wsl.json"
    original = json.loads(archive.read_bytes())["result"]
    source = ROOT / "examples/frontier_sparse_40_131072.sb"
    base, digest = load_circuit(source)
    added = tuple(tuple(gate) for gate in original["added_gates"])
    circuit = Circuit(base.qubits, base.gates + added, "support_scaling")
    if (digest, circuit.qubits, len(circuit.gates), original["final_active_states"]) != (
        original["source_sha256"], 40, 56, STATES
    ):
        raise ValueError("Circuit does not reproduce the archived benchmark")

    factors = list(factorize(circuit))
    counts = [int(np.count_nonzero(np.abs(values) > REFERENCE_ZERO)) for _, values in factors]
    factor_norms = [math.fsum(abs(complex(value)) ** 2 for value in values)
                    for _, values in factors]
    reference_count = math.prod(counts)
    reference_norm = math.prod(factor_norms)
    stats = EvolutionStats()
    started = perf_counter()
    state = evolve(circuit, support_cap=STATES, memory_budget_bytes=STATES * 512,
                   max_seconds=120, stats=stats)
    evolution_seconds = perf_counter() - started
    started = perf_counter()
    error, minimum_reference = compare(state, factors)
    compared_seconds = perf_counter() - started
    passed = (len(state) == stats.peak_support == reference_count == STATES
              and minimum_reference > REFERENCE_ZERO
              and abs(reference_norm - 1) <= TOLERANCE and error <= TOLERANCE)
    report = dict(status="PASS" if passed else "FAIL", revision=suite._revision(),
                  host=platform.system(), architecture=platform.machine(),
                  python=platform.python_version(), cirq_core=version("cirq-core"),
                  numpy=np.__version__, source_sha256=digest, added_gates=added,
                  archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  qubits=40, gates=56,
                  components=[dict(qubits=indices, active_states=count, norm=norm)
                              for (indices, _), count, norm in zip(factors, counts, factor_norms)],
                  reference_active_states=reference_count, reference_norm=reference_norm,
                  sharkbyte_peak_states=stats.peak_support, compared_amplitudes=len(state),
                  max_complex_amplitude_error=error, minimum_reference_magnitude=minimum_reference,
                  amplitude_tolerance=TOLERANCE, component_zero_threshold=REFERENCE_ZERO,
                  sharkbyte_evolution_seconds=evolution_seconds, comparison_seconds=compared_seconds)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")
    print(report["status"], len(state), "amplitudes", "maximum error", error)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
