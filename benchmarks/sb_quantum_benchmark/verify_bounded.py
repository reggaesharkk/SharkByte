"""Replay deletion witnesses independently of the selection algorithm."""
from fractions import Fraction
import time

from .sparse_backend import Circuit, evolve, validate, _check_deadline, MAX_WALL_SECONDS


def replay(circuit, certificate, *, support_cap=None, memory_budget_bytes=64*1024*1024,
           max_seconds=30):
    if not 0 < max_seconds <= MAX_WALL_SECONDS:
        raise ValueError("invalid replay deadline")
    deadline = time.monotonic() + max_seconds
    if support_cap is None:
        support_cap = min(1 << circuit.qubits, memory_budget_bytes//512)
    validate(circuit, support_cap=support_cap, memory_budget_bytes=memory_budget_bytes)
    interval = certificate["interval"]
    protected = certificate["protected"]
    if type(interval) is not int or interval < 1 or any(
        type(i) is not int or not 0 <= i < 1 << circuit.qubits for i in protected
    ) or protected != sorted(set(protected)):
        raise ValueError("invalid schedule or protected coordinates")
    events_list = certificate["events"]
    if not isinstance(events_list, list) or any(not isinstance(e, dict) for e in events_list):
        raise ValueError("invalid event sequence")
    budget = Fraction(certificate["budget"])
    ticks = certificate["ticks_per_budget"]
    if not 0 < budget < 1 or type(ticks) is not int or ticks != 2**32:
        raise ValueError("invalid budget scale")
    total = 0
    events = iter(certificate["events"])
    event = next(events, None)
    state = {0: 1+0j}
    for index, gate in enumerate(circuit.gates, 1):
        state = evolve(Circuit(circuit.qubits, (gate,)), initial_state=state,
                       support_cap=support_cap, memory_budget_bytes=memory_budget_bytes,
                       max_seconds=deadline-time.monotonic())
        if event is not None and event["after_gate"] == index:
            if type(event["after_gate"]) is not int or (index % interval and index != len(circuit.gates)):
                raise ValueError("unscheduled event")
            if not event["removed"]:
                raise ValueError("empty deletion event")
            mass = Fraction(0)
            for basis, real, imag in event["removed"]:
                _check_deadline(deadline)
                if type(basis) is not int or basis not in state:
                    raise ValueError("invalid or repeated basis")
                value = state.pop(basis)
                if basis in certificate["protected"] or (value.real.hex(), value.imag.hex()) != (real, imag):
                    raise ValueError("invalid deletion witness")
                mass += Fraction(value.real)**2 + Fraction(value.imag)**2
            charge = event["ticks"]
            if type(charge) is not int or charge <= 0 or mass > (budget * charge / ticks)**2 or not state:
                raise ValueError("invalid event charge")
            if mass <= (budget*(charge-1)/ticks)**2:
                raise ValueError('charge exceeds minimum')
            total += charge
            event = next(events, None)
    if event is not None or total > ticks or Fraction(certificate["charged_l2"]) != budget*total/ticks:
        raise ValueError("invalid cumulative ledger")
    _check_deadline(deadline)
    return state

if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    from .frontier30 import load_circuit

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    circuit, digest = load_circuit(args.source)
    record = json.loads(args.receipt.read_text())
    if digest != record["source_sha256"]:
        raise ValueError("source digest mismatch")
    recovered = replay(circuit, record["certificate"])
    if len(recovered) != record["final_support"]:
        raise ValueError("final support mismatch")
    print("Verified source, deletions, cumulative charge and final support")
