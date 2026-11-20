"""Bounded input and bit encoding for the H3 research experiment."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import re
import struct

ORDER = "H: complex sum, complex difference, historical real multiply"
ASSUMPTIONS = "finite binary64, nearest-even, gradual underflow, separate operations"
COEFFICIENT_BITS = "3fe6a09e667f3bcc"
GRID = 2**1100


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def sources():
    names = ("h3_format", "h3_generate", "h3_verify", "h3_run",
             "hadamard_foundations", "replay_hadamard_foundations")
    return {name: hashlib.sha256(Path(__file__).with_name(name+".py")
                                 .read_text(encoding="utf-8").encode()).hexdigest()
            for name in names}


def require(condition, reason="invalid H3 record"):
    if not condition:
        raise ValueError(reason)


def decode(token):
    require(isinstance(token, str) and re.fullmatch("[0-9a-f]{16}", token))
    value = struct.unpack(">d", bytes.fromhex(token))[0]
    require(math.isfinite(value), "nonfinite coordinate")
    return value


def encode(state):
    return [[i, struct.pack(">d", z.real).hex(), struct.pack(">d", z.imag).hex()]
            for i, z in sorted(state.items())]


def rows(entries, size):
    require(isinstance(entries, list) and len(entries) <= size)
    result = {}
    for i, real, imag in entries:
        require(type(i) is int and 0 <= i < size and i not in result)
        result[i] = complex(decode(real), decode(imag))
    return result


def request(source):
    require(isinstance(source, str) and len(source) <= 32768)
    def unique(pairs):
        result = dict(pairs)
        require(len(result) == len(pairs), "duplicate source member")
        return result
    data = json.loads(source, object_pairs_hook=unique)
    require(isinstance(data, dict) and set(data) == {"qubits", "initial", "budget", "gates"})
    n = data["qubits"]
    require(type(n) is int and 1 <= n <= 8, "width outside experiment domain")
    size = 1 << n
    initial = rows(data["initial"], size)
    raw_budget = data["budget"]
    require(isinstance(raw_budget, str) and re.fullmatch(r"[0-9]{1,400}(?:/[0-9]{1,400})?", raw_budget))
    budget = Fraction(raw_budget)
    gates = data["gates"]
    require(isinstance(gates, list) and len(gates) <= 64, "gate limit exceeded")
    for gate in gates:
        require(isinstance(gate, list) and len(gate) == 3)
        op, wires, delete = gate
        require(op in ("x", "z", "cx", "h"))
        for indices, limit in ((wires, n), (delete, size)):
            require(isinstance(indices, list) and len(indices) <= limit)
            require(all(type(i) is int and 0 <= i < limit for i in indices))
            require(len(set(indices)) == len(indices))
        require(len(wires) == (2 if op == "cx" else 1))
    return size, initial, budget, gates


def identity(state):
    return digest([[i, str(Fraction(z.real)), str(Fraction(z.imag))]
                   for i, z in sorted(state.items()) if z])
