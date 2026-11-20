"""Independent dense H3 replay and exact ideal-prefix comparison."""
from fractions import Fraction as Q
from math import isqrt
from time import monotonic

from .h3_format import (ASSUMPTIONS, COEFFICIENT_BITS, GRID, ORDER, decode,
                        digest, identity, request, require, rows, sources)

ZERO = (Q(0), Q(0))


def coordinates(z):
    return Q(z.real), Q(z.imag)


def norm2(vector):
    return sum(x*x for pair in vector for x in pair)


def upper_root(value):
    numerator = value.numerator << 2200
    denominator = value.denominator
    root = isqrt(numerator // denominator)
    if root*root*denominator != numerator:
        root += 1
    return Q(root, GRID)


def rounded(x):
    if not x:
        return Q(0)
    magnitude = abs(x)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length()
    if magnitude < Q(2)**exponent:
        exponent -= 1
    quantum = Q(2)**max(-1074, exponent-52)
    result = round(x/quantum)*quantum
    require(abs(result) < 2**1024, "nonfinite replay intermediate")
    return result


def difference(left, right, subtract):
    return tuple(a-b if subtract else a+b for a,b in zip(left,right))


def ideal_within(actual, ideal, h_count, initial_mass, allowance):
    # The exact ideal vector is ideal * 2^(-h_count/2).
    factor = Q(1, 2**(h_count//2))
    dot = sum(a*b for left,right in zip(actual,ideal) for a,b in zip(left,right))
    excess = norm2(actual) + initial_mass - allowance**2
    if h_count % 2 == 0:
        return excess <= 2*dot*factor
    radical = dot*factor
    if radical >= 0:
        return excess <= 0 or excess**2 <= 2*radical**2
    return excess < 0 and excess**2 >= 2*radical**2


def verify(source, ledger, *, seconds=20):
    deadline = monotonic() + seconds
    size, initial, budget, gates = request(source)
    expected = {"source_sha256": digest(source), "modules": sources(),
                "coefficient_bits": COEFFICIENT_BITS, "order": ORDER,
                "assumptions": ASSUMPTIONS, "budget": str(budget)}
    require(set(ledger) == set(expected) | {"initial_norm_squared", "steps", "decision", "final"})
    for key, value in expected.items():
        require(ledger[key] == value, "ledger binding mismatch: "+key)
    c = Q(decode(COEFFICIENT_BITS))
    u = Q(1, 2**53)
    relative = Q(799, 1000)*u
    require((1-relative)**2 < 2*c*c < 1)
    require((1+relative)*(1+u)**2 < 1+3*u)

    actual = [coordinates(initial.get(i, 0j)) for i in range(size)]
    ideal = actual.copy()
    initial_mass = norm2(actual)
    require(ledger["initial_norm_squared"] == str(initial_mass))
    require(len(ledger["steps"]) == len(gates), "missing or extra gate event")
    total = Q(0)
    h_count = 0
    last = initial
    for (op, wires, delete), event in zip(gates, ledger["steps"]):
        require(monotonic() < deadline, "replay deadline")
        bound = upper_root(Q(norm2(actual)))
        flag = 1 << wires[0]
        pairs = 0
        if op == "h":
            h_count += 1
            for i in range(size):
                if i & flag:
                    continue
                j = i | flag
                left, right = actual[i], actual[j]
                pairs += (left != ZERO or right != ZERO)
                actual[i] = tuple(rounded(rounded(x)*c) for x in difference(left,right,False))
                actual[j] = tuple(rounded(rounded(x)*c) for x in difference(left,right,True))
                left, right = ideal[i], ideal[j]
                ideal[i], ideal[j] = difference(left,right,False), difference(left,right,True)
        elif op == "z":
            for i in range(size):
                if i & flag:
                    actual[i] = tuple(-v for v in actual[i])
                    ideal[i] = tuple(-v for v in ideal[i])
        else:
            target = flag if op == "x" else 1 << wires[1]
            for i in range(size):
                j = i ^ target
                if i < j and (op == "x" or i & flag):
                    actual[i], actual[j] = actual[j], actual[i]
                    ideal[i], ideal[j] = ideal[j], ideal[i]
        gate_charge = 3*u*bound + upper_root(Q(pairs))/2**1074 if op == "h" else Q(0)
        removed = norm2(actual[i] for i in delete)
        deletion = upper_root(Q(removed))
        for i in delete:
            actual[i] = ZERO
        total += gate_charge + deletion
        charges = {"norm_upper": str(bound), "pairs": pairs, "arithmetic": str(gate_charge),
                   "deleted_mass": str(removed), "deletion": str(deletion), "total": str(total)}
        require(set(event) == set(charges) | {"post"})
        for key, value in charges.items():
            require(type(event[key]) is type(value) and event[key] == value, "invalid "+key)
        last = rows(event["post"], size)
        require({i: coordinates(z) for i,z in last.items() if z} ==
                {i: pair for i,pair in enumerate(actual) if pair != ZERO}, "forged post-state")
        require(ideal_within(actual, ideal, h_count, initial_mass, total),
                "FAIL exact ideal prefix exceeds cumulative charge")
    require(ledger["final"] == identity(last), "final state mismatch")
    decision = "PASS" if total <= budget else "FAIL"
    require(ledger["decision"] == decision, "budget decision mismatch")
    require(monotonic() < deadline, "replay deadline")
    return decision
