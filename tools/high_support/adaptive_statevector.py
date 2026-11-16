"""Experimental exact sparse/dense switching driver; not a production backend."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from sparse_backend import (
    ANGLE_LIMIT, Circuit, CircuitError, ResourceLimitError, evolve as sparse_evolve,
    validate as validate_circuit,
)
from dense_statevector import evolve as dense_evolve


DEFAULT_SPARSE_BYTES_PER_AMPLITUDE = 512
DEFAULT_DENSE_PEAK_BYTES_PER_BASIS = 48


@dataclass
class AdaptiveStats:
    representation: str = "sparse-dict"
    peak_support: int = 1
    peak_estimated_bytes: int = 0
    transitions: list[dict] = field(default_factory=list)
    gate_trace: list[dict] = field(default_factory=list)
    initialization_seconds: float = 0.0
    evolution_seconds: float = 0.0


def _estimated_dense_peak(qubits, bytes_per_basis):
    return (1 << qubits) * bytes_per_basis


def _projected_sparse_support(state, gate):
    if gate[0].lower() in ("h", "rx", "ry"):
        bit = 1 << gate[1]
        return 2 * len({basis & ~bit for basis in state})
    return len(state)


def evolve_adaptive(circuit: Circuit, *, support_cap: int,
                    memory_budget_bytes: int,
                    max_seconds: float = 300.0,
                    dense_enter_density: float = 0.12,
                    dense_leave_density: float = 0.04,
                    sparse_bytes_per_amplitude: int = DEFAULT_SPARSE_BYTES_PER_AMPLITUDE,
                    dense_peak_bytes_per_basis: int = DEFAULT_DENSE_PEAK_BYTES_PER_BASIS,
                    stats: AdaptiveStats | None = None,
                    progress_callback=None):
    """Evolve exactly and switch only when estimated coexistence fits the budget.

    Dense selection is bounded by ``dense_peak_bytes_per_basis * 2**qubits``.
    The sparse-byte coefficient is deliberately conservative and describes a
    planning estimate, not a measurement. No amplitudes are threshold-pruned.
    A dense-to-sparse switch counts exact nonzero values only.
    """
    if type(memory_budget_bytes) is not int or memory_budget_bytes <= 0:
        raise CircuitError("memory_budget_bytes must be a positive integer")
    if type(support_cap) is not int or support_cap < 1:
        raise CircuitError("support_cap must be a positive integer")
    if type(sparse_bytes_per_amplitude) is not int or sparse_bytes_per_amplitude < 1:
        raise CircuitError("sparse_bytes_per_amplitude must be positive")
    if type(dense_peak_bytes_per_basis) is not int or dense_peak_bytes_per_basis < 16:
        raise CircuitError("dense_peak_bytes_per_basis must be at least 16")
    if (not math.isfinite(dense_enter_density) or not math.isfinite(dense_leave_density)
            or not 0 <= dense_leave_density < dense_enter_density <= 1):
        raise CircuitError("density thresholds must satisfy 0 <= leave < enter <= 1")
    if (isinstance(max_seconds, bool)
            or not isinstance(max_seconds, (int, float))
            or not math.isfinite(max_seconds) or max_seconds <= 0):
        raise CircuitError("max_seconds must be finite and positive")

    # Syntax and support-cap validation are independent of representation policy.
    validate_circuit(circuit, support_cap=support_cap,
                     memory_budget_bytes=support_cap * sparse_bytes_per_amplitude)
    deadline = time.monotonic() + float(max_seconds)
    total_states = 1 << circuit.qubits
    dense_bytes = _estimated_dense_peak(circuit.qubits, dense_peak_bytes_per_basis)
    initialization_started = time.perf_counter()
    state: dict[int, complex] | np.ndarray = {0: 1.0 + 0.0j}
    support = 1
    sparse_estimate = sparse_bytes_per_amplitude
    if sparse_estimate > memory_budget_bytes:
        raise ResourceLimitError("initial sparse state exceeds configured memory budget")
    if stats is None:
        stats = AdaptiveStats()
    stats.representation = "sparse-dict"
    stats.peak_support = support
    stats.peak_estimated_bytes = sparse_estimate
    stats.transitions.clear()
    stats.gate_trace.clear()
    stats.initialization_seconds = time.perf_counter() - initialization_started
    evolution_started = time.perf_counter()

    def check_time(gate_index):
        if time.monotonic() >= deadline:
            raise ResourceLimitError("adaptive evolution wall-clock limit exceeded", gate_index=gate_index)

    for gate_index, gate in enumerate(circuit.gates):
        check_time(gate_index)
        op = gate[0].lower()
        projected = _projected_sparse_support(state, gate) if isinstance(state, dict) else support
        if projected > support_cap:
            raise ResourceLimitError(
                f"{op.upper()} at gate {gate_index} may exceed support cap {support_cap}",
                gate_index=gate_index, requested_support=projected)

        if isinstance(state, dict):
            sparse_peak = (support + projected) * sparse_bytes_per_amplitude
            predicted_density = projected / total_states
            should_enter_dense = (predicted_density >= dense_enter_density
                                  or sparse_peak > memory_budget_bytes)
            if should_enter_dense and dense_bytes <= memory_budget_bytes:
                transition_peak = max(dense_bytes,
                                      support * sparse_bytes_per_amplitude + total_states * 16)
                if transition_peak > memory_budget_bytes:
                    raise ResourceLimitError(
                        "sparse-to-dense transition would exceed configured memory budget",
                        gate_index=gate_index, requested_support=projected)
                dense_state = np.zeros(total_states, dtype=np.complex128)
                for basis, amplitude in state.items():
                    dense_state[basis] = amplitude
                stats.transitions.append({
                    "gate_index": gate_index, "from": "sparse-dict", "to": "dense-complex128",
                    "support": support, "estimated_transition_peak_bytes": transition_peak,
                })
                state = dense_state
                stats.representation = "dense-complex128"
            elif sparse_peak > memory_budget_bytes:
                raise ResourceLimitError(
                    "sparse gate would exceed memory budget and dense representation is not safe",
                    gate_index=gate_index, requested_support=projected)

        if isinstance(state, dict):
            remaining = max(0.001, deadline - time.monotonic())
            # One-gate calls reuse the original exact sparse kernel. No gate
            # semantics are reimplemented in this experimental dispatcher.
            state = sparse_evolve(
                Circuit(circuit.qubits, (gate,), circuit.name), support_cap=support_cap,
                memory_budget_bytes=support_cap * sparse_bytes_per_amplitude,
                max_seconds=min(remaining, 300.0), initial_state=state)
            support = len(state)
            current_estimate = (support + projected) * sparse_bytes_per_amplitude
        else:
            state = dense_evolve(circuit.qubits, (gate,), initial_state=state,
                                 copy_initial_state=False)
            if op in ("h", "rx", "ry"):
                support = int(np.count_nonzero(state))
            current_estimate = dense_bytes

            if support > support_cap:
                raise ResourceLimitError("dense gate exceeded support cap", gate_index=gate_index,
                                         requested_support=support)
            density = support / total_states
            if density <= dense_leave_density:
                sparse_estimate = support * sparse_bytes_per_amplitude
                transition_peak = (total_states * 16 + support *
                                   (sparse_bytes_per_amplitude + 8))
                if (sparse_estimate < total_states * 16
                        and transition_peak <= memory_budget_bytes):
                    nonzero = np.flatnonzero(state)
                    sparse_state = {int(basis): complex(state[basis]) for basis in nonzero}
                    stats.transitions.append({
                        "gate_index": gate_index, "from": "dense-complex128", "to": "sparse-dict",
                        "support": support, "estimated_transition_peak_bytes": transition_peak,
                    })
                    state = sparse_state
                    stats.representation = "sparse-dict"
                    current_estimate = support * sparse_bytes_per_amplitude

        check_time(gate_index)
        stats.peak_support = max(stats.peak_support, support)
        stats.peak_estimated_bytes = max(stats.peak_estimated_bytes, current_estimate)
        stats.gate_trace.append({
            "gate_index": gate_index, "representation": stats.representation,
            "active_states": support, "estimated_bytes": current_estimate,
        })
        if progress_callback is not None:
            progress_callback(gate_index + 1, len(circuit.gates), support,
                              stats.representation)
    stats.evolution_seconds = time.perf_counter() - evolution_started
    return state


def to_dense(state, qubits):
    if isinstance(state, np.ndarray):
        return state
    result = np.zeros(1 << qubits, dtype=np.complex128)
    for basis, amplitude in state.items():
        result[basis] = amplitude
    return result
