"""Software binary64 operations for the restricted H4 experiment."""
from fractions import Fraction

SIGN = 1 << 63
MASK = SIGN - 1
FRACTION = (1 << 52) - 1
COEFFICIENT = 0x3fe6a09e667f3bcc
MAX_FINITE = 0x7fefffffffffffff


def magnitude_units(word):
    """Decode absolute magnitude in units of 2**-1074."""
    exponent = (word >> 52) & 2047
    tail = word & FRACTION
    if exponent == 2047:
        raise ValueError("nonfinite binary64")
    return ((1 << 52) | tail) << (exponent-1) if exponent else tail


def units(word):
    magnitude = magnitude_units(word)
    return -magnitude if word & SIGN else magnitude


def pack(magnitude, denominator_shift, negative):
    """Round a nonnegative dyadic measured in minimum-subnormal units."""
    shift = max(0, magnitude.bit_length()-denominator_shift-53)
    quantum = 1 << (shift+denominator_shift)
    significand, remainder = divmod(magnitude, quantum)
    if 2*remainder > quantum or (2*remainder == quantum and significand & 1):
        significand += 1
    if significand == 1 << 53:
        significand >>= 1
        shift += 1
    if shift >= 2046:
        raise ValueError("binary64 overflow")
    exponent = shift+1 if significand >= 1 << 52 else 0
    return (SIGN if negative else 0) | (exponent << 52) | (significand & FRACTION)


def add(left, right):
    value = units(left)+units(right)
    return pack(abs(value), 0, value < 0 or (not value and left == right == SIGN))


def multiply(word):
    # The historical coefficient is exactly 1592262918131443 / 2**51.
    return pack(magnitude_units(word)*1592262918131443, 51, bool(word & SIGN))


def step(state, op, wires):
    flag = 1 << wires[0]
    if op == "h":
        return [tuple(multiply(add(a, b ^ (SIGN if i & flag else 0)))
                      for a, b in zip(state[i & ~flag], state[i | flag]))
                for i in range(len(state))]
    if op == "z":
        return [tuple(x ^ SIGN for x in pair) if i & flag else pair
                for i, pair in enumerate(state)]
    if op == "x":
        return [state[i ^ flag] for i in range(len(state))]
    target = 1 << wires[1]
    return [state[i ^ target] if i & flag else state[i] for i in range(len(state))]
