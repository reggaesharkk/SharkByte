"""Exact replay of the single-pair research record."""
from fractions import Fraction as Q
import math
import struct


def verify(record):
    def require(condition):
        if not condition:
            raise ValueError("Hadamard replay mismatch")

    def decode(bits):
        value = struct.unpack(">d", bytes.fromhex(bits))[0]
        require(math.isfinite(value))
        return Q(value)

    def round_binary64(x):
        if not x:
            return x
        a = abs(x)
        e = a.numerator.bit_length() - a.denominator.bit_length()
        if a < Q(2)**e:
            e -= 1
        step = Q(2)**max(e - 52, -1074)
        rounded = round(x / step) * step
        require(abs(rounded) < 2**1024)
        return rounded

    x = list(map(decode, record["input_bits"]))
    y = list(map(decode, record["output_bits"]))
    require(len(x) == len(y) == 4)
    require(record["coefficient_bits"] == "3fe6a09e667f3bcc")
    c = decode(record["coefficient_bits"])
    u = Q(1, 2**53)
    # Bracket c sqrt(2) using nonnegative rational squares.
    for coefficient, lower, upper in [(c, Q(798,1000), Q(799,1000)),
                                      (Q(6369051672525773, 2**53), Q(615,1000), Q(616,1000))]:
        if coefficient == c:
            require((1-upper*u)**2 < 2*c*c < (1-lower*u)**2)
        else:
            require((1+lower*u)**2 < 2*coefficient**2 < (1+upper*u)**2)
        require((1+u)**2 * (1+upper*u) - 1 < 3*u)
    s = [x[0]+x[2], x[1]+x[3], x[0]-x[2], x[1]-x[3]]
    require(y == [round_binary64(round_binary64(z)*c) for z in s])
    norm = sum(a*a for a in x)
    require(Q(record["input_norm_squared"]) == norm)
    rel, absolute = Q(record["relative_charge"]), Q(record["absolute_charge"])
    require(rel == 3*u and absolute == Q(1, 2**1074))
    require(record["operations"] == ["complex add", "complex subtract", "complex times real"])
    require(record["assumptions"] == "binary64 nearest-even gradual underflow, separate operations")
    # Rational outward enclosure of sqrt(2); compare squared error to a
    # lower enclosure of the squared allowance.
    scale = 2**5000
    root = math.isqrt(2*scale**2)
    dot = sum(a*b for a,b in zip(y,s))
    error_upper = sum(a*a for a in y) + norm - dot * Q(root + (dot < 0), scale)
    norm_root = Q(math.isqrt((norm * scale**2).__floor__()), scale)
    require(error_upper <= (rel*norm_root + absolute)**2)
    return "PASS"
