"""Replay deletion witnesses independently of the selection algorithm."""
from fractions import Fraction

from .sparse_backend import Circuit, evolve


def replay(circuit, certificate):
    budget = Fraction(certificate["budget"])
    ticks = certificate["ticks_per_budget"]
    if not 0 < budget < 1 or ticks != 2**32:
        raise ValueError("invalid budget scale")
    total = 0
    events = iter(certificate["events"])
    event = next(events, None)
    state = {0: 1+0j}
    for index, gate in enumerate(circuit.gates, 1):
        state = evolve(Circuit(circuit.qubits, (gate,)), initial_state=state,
                       support_cap=1 << circuit.qubits,
                       memory_budget_bytes=(1 << circuit.qubits)*512)
        if event and event["after_gate"] == index:
            mass = Fraction(0)
            for basis, real, imag in event["removed"]:
                value = state.pop(basis)
                if basis in certificate["protected"] or (value.real.hex(), value.imag.hex()) != (real, imag):
                    raise ValueError("invalid deletion witness")
                mass += Fraction(value.real)**2 + Fraction(value.imag)**2
            charge = event["ticks"]
            if type(charge) is not int or charge <= 0 or mass > (budget * charge / ticks)**2 or not state:
                raise ValueError("invalid event charge")
            total += charge
            event = next(events, None)
    if event is not None or total > ticks or Fraction(certificate["charged_l2"]) != budget*total/ticks:
        raise ValueError("invalid cumulative ledger")
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
