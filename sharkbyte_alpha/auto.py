"""Opt-in high-support quantum execution from a SharkByte source checkout."""
import random


def evaluate(source, memory_mib):
    if memory_mib <= 0:
        raise ValueError("--memory-mib must be positive")
    try:
        import numpy as np
        from benchmarks.sb_quantum_benchmark.frontier30 import parse_program
        from benchmarks.sb_quantum_benchmark.sparse_backend import ResourceLimitError, sample
        from tools.high_support.adaptive_statevector import AdaptiveStats, evolve_adaptive
    except ImportError as exc:
        raise ValueError("auto requires NumPy and the SharkByte source checkout") from exc

    program = source if "{" in source else "quantum program {\n" + source + "\n}"
    circuit, parsed = parse_program(program)
    stats = AdaptiveStats()
    budget = memory_mib * 1024**2
    result = dict(backend="auto", qubits=circuit.qubits, shots=parsed["shots"],
                  seed=parsed["seed"], memory_budget_bytes=budget, transitions=stats.transitions)
    try:
        state = evolve_adaptive(circuit, support_cap=1 << circuit.qubits,
                                memory_budget_bytes=budget, stats=stats)
        if isinstance(state, dict):
            counts = sample(state, circuit.qubits, shots=parsed["shots"], seed=parsed["seed"])
        else:
            cumulative = np.abs(state)
            np.square(cumulative, out=cumulative)
            np.cumsum(cumulative, out=cumulative)
            rng = random.Random(parsed["seed"])
            counts = {}
            for _ in range(parsed["shots"]):
                basis = cumulative.searchsorted(rng.random() * cumulative[-1], side="right")
                label = format(min(basis, len(state) - 1), f"0{circuit.qubits}b")
                counts[label] = counts.get(label, 0) + 1
        result.update(status="COMPLETED", counts=counts)
    except ResourceLimitError as exc:
        result.update(status="RESOURCE_STOP", gate_index=exc.gate_index, reason=str(exc))
    result["representation"] = stats.representation
    return result
