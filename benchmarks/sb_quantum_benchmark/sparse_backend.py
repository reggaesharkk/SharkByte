"""Exact sparse statevector prototype for structured-circuit research.

This is an isolated experiment, not part of the SharkByte release or CLI.
It stores only nonzero amplitudes and refuses a gate before it can exceed the
configured support estimate. It never truncates amplitudes or returns an
approximation. Qubit 0 is the least-significant basis-index bit.
"""
from __future__ import annotations

import bisect
import cmath
import math
import random
import time
from dataclasses import dataclass
from typing import Iterable


MAX_QUBITS = 40  # representational ceiling; not a feasibility promise
MAX_GATES = 10_000
MAX_SHOTS = 1_000_000
DEFAULT_SUPPORT_CAP = 65_536
ESTIMATED_BYTES_PER_AMPLITUDE = 512
MAX_WALL_SECONDS = 300.0
ANGLE_LIMIT = 4.0 * math.pi
INV_SQRT2 = 1.0 / math.sqrt(2.0)


class CircuitError(ValueError):
    """Invalid circuit or execution limits."""


class ResourceLimitError(RuntimeError):
    """Exact execution was refused before exceeding configured limits."""


@dataclass(frozen=True)
class Circuit:
    qubits: int
    gates: tuple[tuple, ...]
    name: str = "unnamed"


def validate(circuit: Circuit, *, support_cap: int = DEFAULT_SUPPORT_CAP,
             memory_budget_bytes: int = 64 * 1024 * 1024,
             max_gates: int = MAX_GATES) -> None:
    if type(circuit.qubits) is not int or not 1 <= circuit.qubits <= MAX_QUBITS:
        raise CircuitError(f"qubits must be an integer in [1,{MAX_QUBITS}]")
    if type(support_cap) is not int or support_cap < 1:
        raise CircuitError("support_cap must be a positive integer")
    if type(memory_budget_bytes) is not int or memory_budget_bytes <= 0:
        raise CircuitError("memory budget must be a positive integer")
    if support_cap * ESTIMATED_BYTES_PER_AMPLITUDE > memory_budget_bytes:
        raise ResourceLimitError("support cap exceeds conservative estimated memory budget")
    if type(max_gates) is not int or not 0 <= len(circuit.gates) <= min(max_gates, MAX_GATES):
        raise ResourceLimitError("gate count exceeds configured maximum")
    for index, gate in enumerate(circuit.gates):
        if not isinstance(gate, tuple) or not gate or not isinstance(gate[0], str):
            raise CircuitError(f"gate {index} is malformed")
        op = gate[0].lower()
        if op in {"h", "x", "z"}:
            if len(gate) != 2 or type(gate[1]) is not int:
                raise CircuitError(f"{op} requires one integer qubit")
            _check_qubit(gate[1], circuit.qubits, index)
        elif op in {"cx", "cp"}:
            expected = 3 if op == "cx" else 4
            if len(gate) != expected or type(gate[1]) is not int or type(gate[2]) is not int:
                raise CircuitError(f"{op} requires two distinct integer qubits")
            control, target = gate[1], gate[2]
            _check_qubit(control, circuit.qubits, index)
            _check_qubit(target, circuit.qubits, index)
            if control == target:
                raise CircuitError(f"{op} operands must be distinct")
            if op == "cp":
                angle = gate[3]
                if isinstance(angle, bool) or not isinstance(angle, (int, float)):
                    raise CircuitError("cp angle must be a finite number")
                if not math.isfinite(angle) or abs(angle) > ANGLE_LIMIT:
                    raise CircuitError("cp angle is non-finite or exceeds 4*pi")
        else:
            raise CircuitError(f"unsupported gate: {op}")


def _check_qubit(q: int, n: int, index: int) -> None:
    if not 0 <= q < n:
        raise CircuitError(f"gate {index} qubit index {q} outside [0,{n})")


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ResourceLimitError("wall-clock limit exceeded; no approximate result returned")


def evolve(circuit: Circuit, *, support_cap: int = DEFAULT_SUPPORT_CAP,
           memory_budget_bytes: int = 64 * 1024 * 1024,
           max_seconds: float = 30.0) -> dict[int, complex]:
    validate(circuit, support_cap=support_cap, memory_budget_bytes=memory_budget_bytes)
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)):
        raise CircuitError("max_seconds must be finite and positive")
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= MAX_WALL_SECONDS:
        raise CircuitError(f"max_seconds must be in (0,{MAX_WALL_SECONDS}]")
    deadline = time.monotonic() + float(max_seconds)
    state: dict[int, complex] = {0: 1.0 + 0.0j}
    for gate_no, gate in enumerate(circuit.gates):
        _check_deadline(deadline)
        op = gate[0].lower()
        if op == "h":
            bit = 1 << gate[1]
            pair_bases = {basis & ~bit for basis in state}
            projected_support = 2 * len(pair_bases)
            if projected_support > support_cap:
                raise ResourceLimitError(
                    f"H at gate {gate_no} may expand support to {projected_support}; cap is {support_cap}"
                )
            nxt: dict[int, complex] = {}
            for k, base in enumerate(pair_bases):
                if (k & 1023) == 0:
                    _check_deadline(deadline)
                low = state.get(base, 0.0j)
                high = state.get(base | bit, 0.0j)
                out_low = (low + high) * INV_SQRT2
                out_high = (low - high) * INV_SQRT2
                if out_low != 0.0j:
                    nxt[base] = out_low
                if out_high != 0.0j:
                    nxt[base | bit] = out_high
            state = nxt
        elif op == "x":
            bit = 1 << gate[1]
            state = {basis ^ bit: amp for basis, amp in state.items()}
        elif op == "z":
            bit = 1 << gate[1]
            state = {basis: (-amp if basis & bit else amp) for basis, amp in state.items()}
        elif op == "cx":
            control, target = gate[1], gate[2]
            cb, tb = 1 << control, 1 << target
            state = {
                basis ^ tb if basis & cb else basis: amp
                for basis, amp in state.items()
            }
        elif op == "cp":
            control, target, angle = gate[1], gate[2], float(gate[3])
            mask = (1 << control) | (1 << target)
            phase = cmath.exp(1j * angle)
            state = {
                basis: amp * phase if (basis & mask) == mask else amp
                for basis, amp in state.items()
            }
        if len(state) > support_cap:
            # Defensive postcondition; H has an exact pre-allocation bound.
            raise ResourceLimitError("support cap exceeded; refusing non-exact result")
    _check_deadline(deadline)
    return state


def probabilities(state: dict[int, complex], qubits: int) -> dict[int, float]:
    probs = {basis: float(amp.real * amp.real + amp.imag * amp.imag)
             for basis, amp in state.items()}
    total = math.fsum(probs.values())
    if not math.isfinite(total) or abs(total - 1.0) > 1e-10:
        raise ArithmeticError(f"state norm outside tolerance: {total!r}")
    return probs


def sample(state: dict[int, complex], qubits: int, *, shots: int, seed: int,
           max_seconds: float = 30.0) -> dict[str, int]:
    if type(shots) is not int or not 1 <= shots <= MAX_SHOTS:
        raise CircuitError(f"shots must be in [1,{MAX_SHOTS}]")
    if type(seed) is not int or seed < 0:
        raise CircuitError("seed must be a nonnegative integer")
    if not math.isfinite(max_seconds) or not 0 < max_seconds <= MAX_WALL_SECONDS:
        raise CircuitError("sampling wall-clock limit is invalid")
    deadline = time.monotonic() + float(max_seconds)
    probs = probabilities(state, qubits)
    bases = sorted(probs)
    cumulative: list[float] = []
    total = 0.0
    for probability in (probs[basis] for basis in bases):
        total += probability
        cumulative.append(total)
    if not cumulative or cumulative[-1] <= 0.0:
        raise ArithmeticError("empty or zero-probability state")
    rng = random.Random(seed)
    counts: dict[str, int] = {}
    for shot in range(shots):
        if (shot & 4095) == 0:
            _check_deadline(deadline)
        draw = rng.random() * cumulative[-1]
        pos = min(bisect.bisect_right(cumulative, draw), len(bases) - 1)
        label = format_basis(bases[pos], qubits)
        counts[label] = counts.get(label, 0) + 1
    _check_deadline(deadline)
    return counts


def format_basis(basis: int, qubits: int) -> str:
    return "".join("1" if basis & (1 << q) else "0" for q in range(qubits - 1, -1, -1))


def structured_frontier_circuit(qubits: int, *, theta: float = math.pi / 3.0) -> Circuit:
    """Sparse, nonuniform, entangled family; fanout entangles remaining qubits."""
    if type(qubits) is not int or not 2 <= qubits <= MAX_QUBITS:
        raise CircuitError("structured family supports 2..40 qubits")
    gates: list[tuple] = [("h", 0), ("h", 1), ("cp", 0, 1, theta), ("h", 0)]
    gates.extend(("cx", 1, target) for target in range(2, qubits))
    gates.append(("cp", 0, qubits - 1, 0.37))
    return Circuit(qubits, tuple(gates), f"sparse-nonuniform-entangled-{qubits}q")


def structured_analytic_reference(qubits: int, *, theta: float = math.pi / 3.0) -> dict[int, complex]:
    """Closed-form solution of structured_frontier_circuit, derived by hand.

    The initial four amplitudes are transformed by H(q0) after CP(q0,q1).
    CNOT fanout maps the q1=1 branch to the all-high-bit pattern. This oracle
    does not call the sparse evolution kernel.
    """
    if type(qubits) is not int or not 2 <= qubits <= MAX_QUBITS:
        raise CircuitError("analytic family reference supports 2..40 qubits")
    common = INV_SQRT2
    branch_a = (1.0 + cmath.exp(1j * theta)) / (2.0 * math.sqrt(2.0))
    branch_b = (1.0 - cmath.exp(1j * theta)) / (2.0 * math.sqrt(2.0))
    fanout_base = sum(1 << q for q in range(1, qubits))
    branch_b_basis = fanout_base | 1
    return {
        0: common,
        fanout_base: branch_a,
        branch_b_basis: branch_b * cmath.exp(1j * 0.37),
    }


def inverse_circuit(circuit: Circuit) -> Circuit:
    inverse = []
    for gate in reversed(circuit.gates):
        if gate[0].lower() == "cp":
            inverse.append(("cp", gate[1], gate[2], -float(gate[3])))
        else:
            # H, X, Z, and CX are self-inverse.
            inverse.append(gate)
    return Circuit(circuit.qubits, tuple(inverse), circuit.name + "-inverse")


def hadamard_support_adversary(qubits: int) -> Circuit:
    return Circuit(qubits, tuple(("h", q) for q in range(qubits)), f"dense-support-adversary-{qubits}q")


def qiskit_statevector(circuit: Circuit):
    """Build independently from the gate tuple and return a Qiskit statevector."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    qc = QuantumCircuit(circuit.qubits)
    for gate in circuit.gates:
        op = gate[0].lower()
        if op == "h":
            qc.h(gate[1])
        elif op == "x":
            qc.x(gate[1])
        elif op == "z":
            qc.z(gate[1])
        elif op == "cx":
            qc.cx(gate[1], gate[2])
        elif op == "cp":
            qc.cp(float(gate[3]), gate[1], gate[2])
    return Statevector.from_instruction(qc).data


def compare_qiskit(circuit: Circuit, sparse_state: dict[int, complex]) -> dict:
    """Compare full basis arrays after removing one global phase."""
    import cmath

    dense = qiskit_statevector(circuit)
    reference = [sparse_state.get(i, 0.0j) for i in range(1 << circuit.qubits)]
    overlap = sum(a.conjugate() * complex(b) for a, b in zip(reference, dense))
    phase = cmath.phase(overlap) if abs(overlap) else 0.0
    rotated = [complex(x) * cmath.exp(-1j * phase) for x in dense]
    max_amp = max((abs(a - b) for a, b in zip(reference, rotated)), default=0.0)
    p_sparse = [abs(a) ** 2 for a in reference]
    p_dense = [abs(a) ** 2 for a in dense]
    return {
        "basis_states_compared": len(reference),
        "global_phase_radians": phase,
        "max_complex_amplitude_error_global_phase_aligned": max_amp,
        "max_probability_error": max(abs(a - b) for a, b in zip(p_sparse, p_dense)),
        "l1_probability_error": math.fsum(abs(a - b) for a, b in zip(p_sparse, p_dense)),
        "qiskit_state_norm": math.fsum(p_dense),
        "status": "PASS" if max_amp <= 2e-10 and math.fsum(abs(a - b) for a, b in zip(p_sparse, p_dense)) <= 2e-9 else "FAIL",
    }
