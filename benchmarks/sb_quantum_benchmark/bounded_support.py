"""Budgeted coordinate deletion for validated sparse statevectors."""
import argparse
from fractions import Fraction
import json
from math import isqrt
from pathlib import Path
import time

if __package__:
    from .frontier30 import load_circuit
    from .sparse_backend import Circuit, evolve, validate
else:
    from frontier30 import load_circuit
    from sparse_backend import Circuit, evolve, validate


TICKS = 1 << 32


def compact(state, tick, remaining, protected):
    # Costs use the exact binary values stored in the complex dictionary.
    allowance = tick * remaining
    limit = allowance ** 2
    candidates = []
    for basis, value in state.items():
        if basis in protected or max(abs(value.real), abs(value.imag)) > allowance:
            continue
        mass = Fraction(value.real) ** 2 + Fraction(value.imag) ** 2
        if mass <= limit:
            candidates.append((mass, basis))
    candidates.sort()
    removed_mass = Fraction(0)
    removed = []
    for mass, basis in candidates:
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
        del state[basis]
    return charge, removed


def simulate(circuit, budget, *, support_cap, memory_budget_bytes, max_seconds=30,
             interval=1, protected=()):
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
    state = {0: 1+0j}
    deadline = time.monotonic() + max_seconds
    for index, gate in enumerate(circuit.gates, 1):
        state = evolve(Circuit(circuit.qubits, (gate,)), initial_state=state,
                       support_cap=support_cap, memory_budget_bytes=memory_budget_bytes,
                       max_seconds=deadline-time.monotonic())
        if remaining and (index % interval == 0 or index == len(circuit.gates)):
            charge, removed = compact(state, tick, remaining, protected)
            if removed:
                events.append(dict(after_gate=index, ticks=charge, removed=removed))
                remaining -= charge
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
    args = parser.parse_args()
    circuit, digest = load_circuit(args.source)
    state, certificate = simulate(circuit, args.budget, interval=args.interval,
                                  protected=args.protect, support_cap=args.support_cap,
                                  memory_budget_bytes=args.support_cap*512)
    print(json.dumps(dict(source_sha256=digest, certificate=certificate,
                          final_support=len(state))))
