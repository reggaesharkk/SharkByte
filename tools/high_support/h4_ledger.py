"""Versioned H4 ledger with independent bit-level and ideal-prefix replay."""
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import re
from time import monotonic

from . import h4_bits, h4_replay
from .h3_format import digest, require, request
from .h3_generate import outward
from .h3_verify import ideal_within, upper_root

SCHEMA = "sharkbyte-h4-software-binary64-v1"
ZERO = (0, 0)
RULES = "dense scalar binary64 RN-even; H add/sub then multiply; delete to +0"


def strict_json(text):
    def unique(pairs):
        result = dict(pairs)
        require(len(result) == len(pairs), "duplicate JSON member")
        return result
    return json.loads(text, object_pairs_hook=unique)


def parse(source):
    require(isinstance(source, str) and len(source) <= 32768)
    data = strict_json(source)
    require(isinstance(data, dict) and "initial" in data)
    size, _, budget, gates = request(json.dumps(dict(data, initial=[])))
    state = [ZERO]*size
    seen = set()
    require(isinstance(data["initial"], list) and len(data["initial"]) <= size)
    for i, real, imag in data["initial"]:
        require(type(i) is int and 0 <= i < size and i not in seen)
        seen.add(i)
        require(all(isinstance(x, str) and re.fullmatch("[0-9a-f]{16}", x)
                    for x in (real, imag)))
        state[i] = int(real, 16), int(imag, 16)
        for word in state[i]:
            h4_replay.value(word)
    return state, budget, gates


def words(state):
    return [[f"{a:016x}", f"{b:016x}"] for a, b in state]


def math_digest(state):
    return digest([[i, str(a), str(b)] for i, (a,b) in enumerate(state) if a or b])


def binding(source):
    paths = [Path(__file__).with_name(name+".py") for name in (
        "h4_ledger", "h4_bits", "h4_replay", "h4_run", "h3_format",
        "h3_generate", "h3_verify")]
    return {"schema": SCHEMA, "source_sha256": digest(source), "semantics": RULES,
            "coefficient_bits": "3fe6a09e667f3bcc",
            "modules": {p.name: hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest()
                        for p in paths}}


def generate(source, seconds=20):
    deadline = monotonic()+seconds
    state, budget, gates = parse(source)
    result = binding(source)
    total = Q(0)
    result["steps"] = []
    result["initial_norm_squared"] = str(Q(sum(h4_bits.units(w)**2 for p in state for w in p), 2**2148))
    for op, wires, delete in gates:
        require(monotonic() < deadline, "generation deadline")
        mass = Q(sum(h4_bits.units(w)**2 for p in state for w in p), 2**2148)
        norm = outward(mass)
        flag = 1 << wires[0]
        pairs = len({i & ~flag for i,p in enumerate(state)
                     if any(w & h4_bits.MASK for w in p)}) if op == "h" else 0
        state = h4_bits.step(state, op, wires)
        removed = Q(sum(h4_bits.units(w)**2 for i in delete for w in state[i]), 2**2148)
        for i in delete:
            state[i] = ZERO
        arithmetic = 3*norm/2**53 + outward(Q(pairs))/2**1074 if op == "h" else Q(0)
        deletion = outward(removed)
        total += arithmetic+deletion
        result["steps"].append(event(state, norm, pairs, arithmetic, removed, deletion, total))
    final = finish(state, budget, total,
                   [tuple(Q(h4_bits.units(w), 2**1074) for w in p) for p in state])
    require(monotonic() < deadline, "generation deadline")
    return dict(result, **final)


def event(state, norm, pairs, arithmetic, mass, deletion, total):
    return {"post_bits": words(state), "norm_upper": str(norm), "pairs": pairs,
            "arithmetic": str(arithmetic), "deleted_mass": str(mass),
            "deletion": str(deletion), "total": str(total)}


def finish(state, budget, total, exact):
    return {"budget": str(budget), "decision": "PASS" if total <= budget else "FAIL",
            "final_bits_sha256": digest(words(state)),
            "final_math_sha256": math_digest(exact)}


def values(state):
    return [tuple(map(h4_replay.value, pair)) for pair in state]


def verify(source, ledger, seconds=20):
    deadline = monotonic()+seconds
    state, budget, gates = parse(source)
    expected = binding(source)
    coefficient = h4_replay.value(h4_replay.COEFFICIENT)
    u = Q(1, 2**53)
    relative = Q(799, 1000)*u
    require((1-relative)**2 < 2*coefficient**2 < 1
            and (1+relative)*(1+u)**2 < 1+3*u, "invalid coefficient bound")
    ideal = values(state)
    initial_mass = sum(x*x for p in ideal for x in p)
    expected["initial_norm_squared"] = str(initial_mass)
    require(isinstance(ledger, dict) and isinstance(ledger.get("steps"), list)
            and len(ledger["steps"]) == len(gates))
    total = Q(0)
    h_count = 0
    expected["steps"] = []
    for (op, wires, delete), claimed in zip(gates, ledger["steps"]):
        require(monotonic() < deadline, "replay deadline")
        exact = values(state)
        norm = upper_root(sum((x*x for p in exact for x in p), Q()))
        flag = 1 << wires[0]
        pairs = 0
        if op == "h":
            h_count += 1
            for i in range(len(state)):
                if i & flag:
                    continue
                j = i+flag
                pairs += any(exact[i]) or any(exact[j])
                left, right = ideal[i], ideal[j]
                ideal[i] = tuple(a+b for a,b in zip(left,right))
                ideal[j] = tuple(a-b for a,b in zip(left,right))
        elif op == "z":
            ideal = [tuple(-x for x in p) if i & flag else p for i,p in enumerate(ideal)]
        else:
            flip = flag if op == "x" else 1 << wires[1]
            ideal = [ideal[i ^ flip] if op == "x" or i & flag else p for i,p in enumerate(ideal)]
        state = h4_replay.step(state, op, wires)
        removed = sum((h4_replay.value(w)**2 for i in delete for w in state[i]), Q())
        for i in delete:
            state[i] = ZERO
        deletion = upper_root(removed)
        arithmetic = 3*norm/2**53 + upper_root(Q(pairs))/2**1074 if op == "h" else Q()
        total += deletion+arithmetic
        actual = event(state, norm, pairs, arithmetic, removed, deletion, total)
        require(digest(actual) == digest(claimed), "operation or charge mismatch")
        require(ideal_within(values(state), ideal, h_count, initial_mass, total),
                "FAIL exact ideal-prefix enclosure")
        expected["steps"].append(actual)
    expected.update(finish(state, budget, total, values(state)))
    require(digest(expected) == digest(ledger), "receipt binding mismatch")
    require(monotonic() < deadline, "replay deadline")
    return expected["decision"]
