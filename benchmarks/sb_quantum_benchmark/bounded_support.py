"""Budgeted coordinate deletion for validated sparse statevectors."""
import argparse
from fractions import Fraction
import json
import heapq
from math import isqrt
from pathlib import Path
import time

if __package__:
    from .frontier30 import load_circuit
    from .sparse_backend import Circuit, evolve, validate, ResourceLimitError, _check_deadline, MAX_WALL_SECONDS
else:
    from frontier30 import load_circuit
    from sparse_backend import Circuit, evolve, validate, ResourceLimitError, _check_deadline, MAX_WALL_SECONDS


TICKS = 1 << 32


def compact(state, tick, remaining, protected, *, deadline=float("inf"), scratch_bytes=None):
    # Estimates include candidate rationals and a possible witness per candidate.
    # Check each heap operation so ordering can be interrupted between entries.
    # Costs use the exact binary values stored in the complex dictionary.
    allowance = tick * remaining
    limit = allowance ** 2
    candidates = []
    for basis, value in state.items():
        _check_deadline(deadline)
        if basis in protected or max(abs(value.real), abs(value.imag)) > allowance:
            continue
        mass = Fraction(value.real) ** 2 + Fraction(value.imag) ** 2
        if mass <= limit:
            if scratch_bytes is not None and (len(candidates)+1)*1024 > scratch_bytes:
                raise ResourceLimitError("estimated compaction workspace exceeds memory budget")
            heapq.heappush(candidates, (mass, basis))
    removed_mass = Fraction(0)
    removed = []
    while candidates:
        _check_deadline(deadline)
        mass, basis = heapq.heappop(candidates)
        if removed_mass + mass > limit or len(removed) + 1 == len(state):
            break
        removed_mass += mass
        value = state[basis]
        removed.append([basis, value.real.hex(), value.imag.hex()])
    if not removed:
        return 0, []
    ratio = removed_mass / tick ** 2
    charge = isqrt(ratio.numerator // ratio.denominator)
    charge += charge ** 2 < ratio
    for basis, _, _ in removed:
        _check_deadline(deadline)
        del state[basis]
    return charge, removed


def simulate(circuit, budget, *, support_cap, memory_budget_bytes, max_seconds=30,
             interval=1, protected=(), progress_callback=None, initial_state=None):
    if not 0 < max_seconds <= MAX_WALL_SECONDS:
        raise ValueError('invalid execution deadline')
    budget = Fraction(budget)
    if not 0 < budget < 1 or type(interval) is not int or interval < 1:
        raise ValueError("require 0 < budget < 1 and positive integer interval")
    protected = frozenset(protected)
    if any(type(i) is not int or not 0 <= i < 1 << circuit.qubits for i in protected):
        raise ValueError("protected index outside register")
    validate(circuit, support_cap=support_cap, memory_budget_bytes=memory_budget_bytes)
    remaining = TICKS
    tick = budget / TICKS
    events = []
    witness_bytes = 0
    if initial_state is None:
        state = {0: 1+0j}
    else:
        if not isinstance(initial_state, dict) or not initial_state:
            raise ValueError("initial_state must be a nonempty basis-to-amplitude dictionary")
        state = dict(initial_state)
        if any(type(basis) is not int or not 0 <= basis < 1 << circuit.qubits
               or not isinstance(value, complex) or value == 0j
               for basis, value in state.items()):
            raise ValueError("invalid initial state")
        if len(state) > support_cap:
            raise ResourceLimitError("initial_state exceeds support cap")
    deadline = time.monotonic() + max_seconds
    for index, gate in enumerate(circuit.gates, 1):
        if witness_bytes + min(support_cap, len(state)*2)*512 > memory_budget_bytes:
            raise ResourceLimitError("estimated kernel and retained witnesses exceed memory budget")
        state = evolve(Circuit(circuit.qubits, (gate,)), initial_state=state,
                       support_cap=support_cap, memory_budget_bytes=memory_budget_bytes,
                       max_seconds=deadline-time.monotonic())
        if remaining and (index % interval == 0 or index == len(circuit.gates)):
            charge, removed = compact(
                state, tick, remaining, protected, deadline=deadline,
                scratch_bytes=memory_budget_bytes-len(state)*512-witness_bytes)
            if removed:
                events.append(dict(after_gate=index, ticks=charge, removed=removed))
                witness_bytes += 512*(1+len(removed))
                remaining -= charge
        if progress_callback is not None:
            progress_callback(index, len(circuit.gates), len(state))
        if time.monotonic() > deadline:
            raise TimeoutError("compaction deadline exceeded")
    return state, dict(budget=str(budget), ticks_per_budget=TICKS, interval=interval,
                       protected=sorted(protected), events=events,
                       charged_l2=str(tick * (TICKS-remaining)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--budget", required=True)
    parser.add_argument("--interval", type=int, default=1)
    parser.add_argument("--protect", type=int, action="append", default=[])
    parser.add_argument("--support-cap", type=int, default=4096)
    parser.add_argument("--memory-mib", type=int, help="estimated state and compaction workspace limit")
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    circuit, digest = load_circuit(args.source)
    state, certificate = simulate(circuit, args.budget, interval=args.interval,
                                  protected=args.protect, support_cap=args.support_cap,
                                  memory_budget_bytes=(args.support_cap*512 if args.memory_mib is None else args.memory_mib*2**20),
                                  max_seconds=args.seconds)
    print(json.dumps(dict(source_sha256=digest, certificate=certificate,
                          final_support=len(state))))
