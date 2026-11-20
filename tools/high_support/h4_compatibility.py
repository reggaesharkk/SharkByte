"""Gate 4b research comparator. Only the pinned candidate-v1 is registered."""
import argparse
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
from math import isqrt
from pathlib import Path
import re
import sys
import tarfile
import tempfile
from time import monotonic

from . import h4_historical_checkout as history

VERSION = "sharkbyte-xz-cx-h-candidate-v1"
IMPLEMENTATION = history.ACCEPTED_FILES["tools/high_support/h4_candidate.py"]
MODULES = {Path(path).name: sha for path, sha in history.ACCEPTED_FILES.items()
           if path.endswith(".py") and not path.endswith("h4_candidate.py")}
SIGN = 1 << 63
COEFFICIENT = Q(1592262918131443, 2**51)
RULE = "dense scalar binary64 RN-even; H add/sub then multiply; delete to +0"


class Unsupported(ValueError):
    """The comparison lies outside the registered contract."""


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(canonical(value).encode("ascii"))


def decode(raw, limit):
    need(type(raw) is bytes and len(raw) <= limit, "byte limit or input type")

    def unique(pairs):
        obj = dict(pairs)
        need(len(obj) == len(pairs), "duplicate member")
        return obj

    value = json.loads(raw.decode("ascii"), object_pairs_hook=unique)
    need(raw == (canonical(value)+"\n").encode("ascii"), "noncanonical JSON")
    return value


def fraction(word):
    exp = (word >> 52) & 2047
    tail = word & ((1 << 52)-1)
    need(exp != 2047, "nonfinite word")
    value = Q(tail) * Q(2)**-1074 if not exp else Q((1 << 52)+tail)*Q(2)**(exp-1075)
    return -value if word & SIGN else value


def rounded(value, negative_zero=False):
    """Round through an exact dyadic grid, independently of H4's bit search."""
    sign = SIGN if value < 0 or (value == 0 and negative_zero) else 0
    x = abs(value)
    if not x:
        return sign
    exponent = x.numerator.bit_length()-x.denominator.bit_length()
    if x < Q(2)**exponent:
        exponent -= 1
    quantum_exp = max(exponent-52, -1074)
    units = round(x/Q(2)**quantum_exp)
    if units == 1 << 53:
        units >>= 1
        quantum_exp += 1
    need(quantum_exp <= 971, "binary64 overflow")
    if units < 1 << 52:
        return sign | units
    return sign | ((quantum_exp+1075) << 52) | (units-(1 << 52))


def pairs_values(words):
    return tuple(tuple(map(fraction, pair)) for pair in words)


def norm2(state):
    return sum((x*x for pair in state for x in pair), Q(0))


def root_upper(value):
    grid = 1 << 1100
    scaled = value*grid*grid
    floor = isqrt(scaled.numerator//scaled.denominator)
    return Q(floor+(floor*floor != scaled), grid)


def gate(state, op, wires, *, exact):
    mask = 1 << wires[0]
    result = []
    for i, pair in enumerate(state):
        on = bool(i & mask)
        if op in ("x", "cx"):
            flip = mask if op == "x" else ((1 << wires[1]) if on else 0)
            result.append(state[i ^ flip])
        elif op == "z":
            result.append(tuple((-x if exact else x ^ SIGN) if on else x for x in pair))
        else:
            left, right = state[i & ~mask], state[i | mask]
            if exact:
                result.append(tuple(a-b if on else a+b for a,b in zip(left,right)))
            else:
                output = []
                for a,b in zip(left,right):
                    operand = b ^ SIGN if on else b
                    summed = rounded(fraction(a)+fraction(operand), a == operand == SIGN)
                    output.append(rounded(fraction(summed)*COEFFICIENT, summed == SIGN))
                result.append(tuple(output))
    return tuple(result)


def within(actual, ideal, h, mass, total):
    # ideal entries are unscaled dyadics, with common scale 2^(-h/2).
    dot = sum((a*b for p,q in zip(actual,ideal) for a,b in zip(p,q)), Q(0))/2**(h//2)
    excess = norm2(actual)+mass-total**2
    if h % 2 == 0:
        return excess <= 2*dot
    if dot >= 0:
        return excess <= 0 or excess**2 <= 2*dot**2
    return excess < 0 and excess**2 >= 2*dot**2


def parse_source(raw):
    data = decode(raw, history.SOURCE_LIMIT)
    need(type(data) is dict and set(data) == {"contract","qubits","initial","gates","budget"},
         "source fields")
    if data["contract"] != VERSION:
        raise Unsupported("unregistered source version")
    n = data["qubits"]
    need(type(n) is int, "width type")
    if not 1 <= n <= 8:
        raise Unsupported("width outside v1")
    budget = data["budget"]
    need(type(budget) is str and re.fullmatch(r"[0-9]{1,400}(?:/[0-9]{1,400})?", budget)
         and str(Q(budget)) == budget, "noncanonical budget")
    state = [(0,0)]*(1 << n)
    previous = -1
    need(type(data["initial"]) is list and len(data["initial"]) <= len(state), "initial rows")
    for row in data["initial"]:
        need(type(row) is list and len(row) == 3, "initial row")
        i,a,b = row
        need(type(i) is int and previous < i < len(state), "initial index order")
        need(all(type(w) is str and re.fullmatch("[0-9a-f]{16}",w) for w in (a,b)), "word encoding")
        state[i] = int(a,16), int(b,16)
        previous = i
    gates = []
    need(type(data["gates"]) is list, "gate list")
    if len(data["gates"]) > 64:
        raise Unsupported("gate count outside v1")
    for entry in data["gates"]:
        need(type(entry) is list and len(entry) == 2, "gate fields")
        op,wires = entry
        if op not in ("x","z","cx","h"):
            raise Unsupported("unregistered operation")
        need(type(wires) is list and len(wires) == (2 if op == "cx" else 1)
             and all(type(w) is int and 0 <= w < n for w in wires)
             and len(set(wires)) == len(wires), "gate wires")
        gates.append((op,tuple(wires)))
    return data, tuple(state), tuple(gates)


@dataclass(frozen=True)
class Trace:
    initial: tuple
    initial_words: tuple
    gates: tuple
    ideal: tuple
    outputs: tuple
    final_math: tuple
    charges: tuple
    budget: Q
    outcome: str
    arithmetic: str = RULE
    normalization: str = "none"


def reconstruct(source, *, seconds=20):
    deadline = monotonic()+seconds
    data, state, gates = parse_source(source)
    initial_words = state
    initial = ideal = pairs_values(state)
    mass = norm2(initial)
    u = Q(1, 2**53)
    relative = Q(799,1000)*u
    need((1-relative)**2 < 2*COEFFICIENT**2 < 1
         and (1+relative)*(1+u)**2 < 1+3*u, "coefficient proof obligation")
    total = Q(0)
    h = 0
    steps, ideal_trace, outputs, charges = [], [], [], []
    for op,wires in gates:
        if monotonic() >= deadline:
            raise Unsupported("replay deadline")
        actual = pairs_values(state)
        bound = root_upper(norm2(actual))
        mask = 1 << wires[0]
        count = sum(bool(any(actual[i]) or any(actual[i | mask]))
                    for i in range(len(state)) if not i & mask) if op == "h" else 0
        charge = 3*u*bound+root_upper(Q(count))/2**1074 if op == "h" else Q(0)
        total += charge
        h += op == "h"
        ideal = gate(ideal,op,wires,exact=True)
        state = gate(state,op,wires,exact=False)
        need(within(pairs_values(state),ideal,h,mass,total), "ideal prefix exceeds bound")
        ideal_trace.append((h,ideal))
        outputs.append(state)
        charges.append((bound,count,charge,total))
        steps.append({"post_bits": hex_words(state), "norm_upper": str(bound), "pairs": count,
                      "arithmetic": str(charge), "deleted_mass": "0", "deletion": "0",
                      "total": str(total)})
    final_math = pairs_values(state)
    norm_words = [[i,str(a),str(b)] for i,(a,b) in enumerate(final_math) if a or b]
    budget = Q(data["budget"])
    success = total <= budget
    internal = canonical(dict(qubits=data["qubits"],initial=data["initial"],
                              gates=[[op,list(w),[]] for op,w in gates],budget=str(budget)))+"\n"
    ledger = {"schema": "sharkbyte-h4-software-binary64-v1", "source_sha256": digest(internal),
              "semantics": RULE, "coefficient_bits": "3fe6a09e667f3bcc", "modules": MODULES,
              "initial_norm_squared": str(mass), "steps": steps, "budget": str(budget),
              "decision": "PASS" if success else "FAIL", "final_bits_sha256": digest(hex_words(state)),
              "final_math_sha256": digest(norm_words)}
    outcome = "VERIFIED_PASS" if success else "VERIFIED_BUDGET_EXCEEDED"
    if monotonic() >= deadline:
        raise Unsupported("replay deadline")
    trace = Trace(initial,initial_words,gates,tuple(ideal_trace),tuple(outputs),final_math,
                  tuple(charges),budget,outcome)
    return trace, {"contract": VERSION, "source_sha256": sha(source),
                   "candidate_sha256": IMPLEMENTATION, "ledger": ledger, "outcome": outcome}


def hex_words(state):
    return [[f"{r:016x}",f"{i:016x}"] for r,i in state]


def verify(version, source, receipt):
    if version != VERSION:
        raise Unsupported("unregistered implementation selector")
    record = decode(receipt, history.RECEIPT_LIMIT)
    trace, expected = reconstruct(source)
    need(canonical(record) == canonical(expected), "independent replay or binding mismatch")
    return trace


def compare_traces(left, right):
    equivalent = (left.initial == right.initial and left.gates == right.gates
                  and left.ideal == right.ideal and left.normalization == right.normalization)
    matching_words = left.initial_words == right.initial_words and left.outputs == right.outputs
    same_arithmetic = left.arithmetic == right.arithmetic
    certificate = (equivalent and matching_words and same_arithmetic
                   and left.charges == right.charges and left.budget == right.budget
                   and left.outcome == right.outcome)
    return {"mathematical": "PASS" if equivalent else "DIFFERENT_OR_UNPROVED",
            "observed_words_equal": matching_words,
            "bit_level": "PASS" if equivalent and matching_words and same_arithmetic else "NOT_ESTABLISHED",
            "arithmetic_contract_equal": same_arithmetic,
            "final_mathematical_state_equal": left.final_math == right.final_math,
            "certificate": "PASS" if certificate else "DIFFERENT_OR_UNPROVED",
            "accuracy": [left.outcome,right.outcome],
            "within_budget_certified": [trace.outcome == "VERIFIED_PASS" for trace in (left,right)],
            "execution_authenticity": "UNAUTHENTICATED",
            "decision": "COMPATIBLE" if certificate else "NOT_ESTABLISHED"}


def compare(left_version, left_source, left_receipt, right_version, right_source, right_receipt):
    if left_version != VERSION or right_version != VERSION:
        raise Unsupported("unregistered implementation selector")
    # Check real pinned Git content without importing any historical or current
    # H4 arithmetic module. CLI users may run the Gate 4a launcher separately.
    with tempfile.TemporaryDirectory(prefix="sharkbyte-h4-compat-") as directory:
        history.extract_pinned(history.historical_archive(), Path(directory))
    left = verify(left_version,left_source,left_receipt)
    right = verify(right_version,right_source,right_receipt)
    return dict(compare_traces(left,right), syntax="PASS",
                archival="PINNED_TREE_AND_INDEPENDENT_REPLAY",
                source_bytes_equal=left_source == right_source,
                registered_versions=[VERSION])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for side in ("left","right"):
        parser.add_argument(side+"_version")
        parser.add_argument(side+"_source", type=Path)
        parser.add_argument(side+"_receipt", type=Path)
    args = parser.parse_args()
    try:
        report = compare(args.left_version,history.read_bytes(args.left_source,history.SOURCE_LIMIT),
                         history.read_bytes(args.left_receipt,history.RECEIPT_LIMIT),
                         args.right_version,history.read_bytes(args.right_source,history.SOURCE_LIMIT),
                         history.read_bytes(args.right_receipt,history.RECEIPT_LIMIT))
        code = 0 if report["decision"] == "COMPATIBLE" else 1
    except (Unsupported, history.HistoryUnavailable, MemoryError) as exc:
        report, code = {"decision":"UNSUPPORTED","reason":str(exc)}, 3
    except (ValueError, TypeError, OSError, ArithmeticError, RecursionError, tarfile.TarError) as exc:
        report, code = {"decision":"INVALID_RECORD","reason":str(exc)}, 2
    print(canonical(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
