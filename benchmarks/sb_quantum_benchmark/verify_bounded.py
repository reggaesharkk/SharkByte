"""Replay deletion witnesses independently of the selection algorithm."""
from fractions import Fraction
import time

from .sparse_backend import Circuit, evolve, validate, _check_deadline, MAX_WALL_SECONDS

MOVING_BRANCH_MODE = "moving-initial-basis-branches-v1"


def _fraction_value(value):
    return (Fraction(*value.real.as_integer_ratio()),
            Fraction(*value.imag.as_integer_ratio()))


def _move_positions(positions, gate, deadline):
    op = gate[0].lower()
    bit = 1 << gate[1] if op in ("x", "z") else None
    control = (1 << gate[1]) if op == "cx" else None
    target = (1 << gate[2]) if op == "cx" else None
    if op not in ("x", "z", "cx"):
        raise ValueError(f"moving-branch protection does not support gate {op}")
    for index, origin in enumerate(positions):
        if index % 256 == 0:
            _check_deadline(deadline)
        basis = positions[origin]
        if op == "x":
            positions[origin] = basis ^ bit
        elif op == "cx" and basis & control:
            positions[origin] = basis ^ target
    return positions


def replay(circuit, certificate, *, support_cap=None, memory_budget_bytes=64*1024*1024,
           max_seconds=30, initial_state=None):
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
    tracking = certificate.get("protection_mode") == MOVING_BRANCH_MODE
    if certificate.get("protection_mode") not in (None, MOVING_BRANCH_MODE):
        raise ValueError("unknown protection mode")
    if tracking:
        if protected:
            raise ValueError("moving-branch mode cannot include fixed protected coordinates")
        origins = certificate.get("protected_branches")
        if (not isinstance(origins, list) or origins != sorted(set(origins))
                or any(type(i) is not int or not 0 <= i < 1 << circuit.qubits for i in origins)):
            raise ValueError("invalid moving-branch origins")
        if any(gate[0].lower() not in {"x", "z", "cx"} for gate in circuit.gates):
            raise ValueError("moving-branch protection does not support mixing or angle gates")
    total = 0
    events = iter(certificate["events"])
    event = next(events, None)
    state = {0: 1+0j} if initial_state is None else dict(initial_state)
    if tracking:
        if any(origin not in state or state[origin] == 0j for origin in origins):
            raise ValueError("protected branch origin is absent from the initial state")
        branch_values = {origin: _fraction_value(state[origin]) for origin in origins}
        positions = {origin: origin for origin in origins}
    for index, gate in enumerate(circuit.gates, 1):
        state = evolve(Circuit(circuit.qubits, (gate,)), initial_state=state,
                       support_cap=support_cap, memory_budget_bytes=memory_budget_bytes,
                       max_seconds=deadline-time.monotonic())
        if tracking:
            op = gate[0].lower()
            if op == "z":
                bit = 1 << gate[1]
                for branch_index, origin in enumerate(origins):
                    if branch_index % 256 == 0:
                        _check_deadline(deadline)
                    if positions[origin] & bit:
                        real, imag = branch_values[origin]
                        branch_values[origin] = (-real, -imag)
            positions = _move_positions(positions, gate, deadline)
            for origin, position in positions.items():
                if position not in state or _fraction_value(state[position]) != branch_values[origin]:
                    raise ValueError(f"protected branch {origin} lost its exact Fraction amplitude")
            protected_positions = set(positions.values())
        else:
            protected_positions = set()
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
                if basis in protected_positions:
                    raise ValueError("protected moving branch was deleted")
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
    if tracking:
        expected_positions = [[origin, positions[origin]] for origin in origins]
        if certificate.get("final_protected_positions") != expected_positions:
            raise ValueError("final moving-branch position map mismatch")
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
