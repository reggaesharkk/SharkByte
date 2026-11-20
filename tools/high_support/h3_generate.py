"""Experimental cumulative ledger producer using native complex operations."""
from fractions import Fraction as Q
from math import isqrt
from time import monotonic

from .hadamard_foundations import enclose, U
from .h3_format import (ASSUMPTIONS, COEFFICIENT_BITS, GRID, ORDER, decode,
                        digest, encode, identity, request, require, sources)


def outward(value):
    scaled = value * GRID**2
    k = isqrt(scaled.numerator // scaled.denominator)
    return Q(k + (k*k < scaled), GRID)


def mass(state):
    return sum((Q(z.real)**2 + Q(z.imag)**2 for z in state.values()), Q(0))


def generate(source, *, seconds=20):
    deadline = monotonic() + seconds
    _, initial, budget, gates = request(source)
    enclose(0j, 0j)
    state = {i: z for i, z in initial.items() if z}
    result = {"source_sha256": digest(source), "modules": sources(),
              "coefficient_bits": COEFFICIENT_BITS, "order": ORDER,
              "assumptions": ASSUMPTIONS, "initial_norm_squared": str(mass(state)),
              "budget": str(budget), "steps": []}
    total = Q(0)
    for op, wires, delete in gates:
        require(monotonic() < deadline, "generation deadline")
        flag = 1 << wires[0]
        norm = outward(mass(state))
        pairs = 0
        if op == "h":
            out = {}
            bases = {i & ~flag for i in state}
            for i in sorted(bases):
                data = enclose(state.get(i, 0j), state.get(i | flag, 0j))
                a, b, c, d = map(decode, data["output_bits"])
                out[i], out[i | flag] = complex(a, b), complex(c, d)
            state = {i: z for i, z in out.items() if z}
            pairs = len(bases)
        elif op == "z":
            state = {i: -z if i & flag else z for i, z in state.items()}
        elif op == "x":
            state = {i ^ flag: z for i, z in state.items()}
        else:
            target = 1 << wires[1]
            state = {i ^ target if i & flag else i: z for i, z in state.items()}
        arithmetic = 3*U*norm + outward(Q(pairs))/2**1074 if op == "h" else Q(0)
        removed = {i: state.pop(i, 0j) for i in delete}
        deleted = mass(removed)
        charge = outward(deleted)
        total += arithmetic + charge
        result["steps"].append({"norm_upper": str(norm), "pairs": pairs,
                                "arithmetic": str(arithmetic), "deleted_mass": str(deleted),
                                "deletion": str(charge), "total": str(total), "post": encode(state)})
    result.update(final=identity(state), decision="PASS" if total <= budget else "FAIL")
    require(monotonic() < deadline, "generation deadline")
    return result
