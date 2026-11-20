"""Standalone research arithmetic for A1 and A2."""
from fractions import Fraction
import math
import struct
import sys

U = Fraction(1, 2**53)
HALF_SUBNORMAL = Fraction(1, 2**1075)
COEFFICIENT = float.fromhex("0x1.6a09e667f3bccp-1")


def sign(a, b):
    """Sign of a + b sqrt(2), for integer or rational components."""
    if a >= 0 and b >= 0:
        return int(bool(a or b))
    if a <= 0 and b <= 0:
        return -1
    difference = a*a - 2*b*b
    return ((difference > 0) - (difference < 0)) * (1 if a > 0 else -1)


def deletion_ticks(a, b, denominator, unit):
    if (any(type(value) is not int for value in (a, b, denominator))
            or denominator <= 0 or not isinstance(unit, Fraction)
            or unit <= 0 or sign(a, b) < 0):
        raise ValueError("invalid mass or tick unit")

    def covers(ticks):
        return sign(denominator * (ticks * unit)**2 - a, -b) >= 0

    if covers(0):
        return 0
    low, high = 0, 1
    while not covers(high):
        low, high = high, 2 * high
    while high - low > 1:
        middle = (high + low) // 2
        if covers(middle):
            high = middle
        else:
            low = middle
    return high


def bits(value):
    return struct.pack(">d", value).hex()


def enclose(low, high):
    """Evaluate the historical complex operation sequence on one pair."""
    tiny = float.fromhex("0x0.0000000000001p-1022")
    if (sys.implementation.name != "cpython" or sys.float_info.mant_dig != 53
            or sys.float_info.radix != 2 or sys.float_info.rounds != 1
            or tiny + tiny == 0 or tiny * COEFFICIENT != tiny
            or 1.0 / math.sqrt(2.0) != COEFFICIENT):
        raise ValueError("UNSUPPORTED environment")
    sums = (low + high, low - high)
    outputs = tuple(value * COEFFICIENT for value in sums)
    components = lambda pair: [part for z in pair for part in (z.real, z.imag)]
    inputs = components((low, high))
    if not all(map(math.isfinite, inputs + components(sums) + components(outputs))):
        raise ValueError("UNSUPPORTED nonfinite coordinate")
    return {
        "input_bits": list(map(bits, inputs)),
        "coefficient_bits": bits(COEFFICIENT),
        "output_bits": list(map(bits, components(outputs))),
        "operations": ["complex add", "complex subtract", "complex times real"],
        "assumptions": "binary64 nearest-even gradual underflow, separate operations",
        "input_norm_squared": str(sum(Fraction(x)**2 for x in inputs)),
        "relative_charge": str(3 * U),
        "absolute_charge": str(2 * HALF_SUBNORMAL),
    }
