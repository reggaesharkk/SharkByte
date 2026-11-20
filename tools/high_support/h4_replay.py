"""Independent replay by searching adjacent finite binary64 encodings."""
from fractions import Fraction as Q

SIGN = 2**63
MAX = 0x7fefffffffffffff
COEFFICIENT = 0x3fe6a09e667f3bcc


def value(word):
    exp, tail = divmod(word % SIGN, 2**52)
    if exp >= 2047:
        raise ValueError("nonfinite binary64")
    number = Q(tail, 2**1074) if exp == 0 else (2**52+tail)*Q(2)**(exp-1075)
    return -number if word >= SIGN else number


def nearest(number, negative_zero=False):
    negative = number < 0 or (number == 0 and negative_zero)
    wanted = abs(number)
    if wanted >= value(MAX) + Q(2)**970:
        raise ValueError("binary64 overflow")
    if not wanted:
        return SIGN if negative else 0
    low, high = 0, MAX
    while low < high:
        mid = (low+high+1)//2
        if value(mid) <= wanted:
            low = mid
        else:
            high = mid-1
    if low < MAX:
        twice = 2*wanted
        midpoint_twice = value(low)+value(low+1)
        if twice > midpoint_twice or (twice == midpoint_twice and low % 2):
            low += 1
    return low + (SIGN if negative else 0)


def step(state, op, wires):
    out = list(state)
    flag = 1 << wires[0]
    if op == "h":
        coefficient = value(COEFFICIENT)
        for i in range(len(state)):
            if i & flag:
                continue
            j = i+flag
            for dest, subtract in ((i, False), (j, True)):
                components = []
                for left, right in zip(state[i], state[j]):
                    rhs = -value(right) if subtract else value(right)
                    both_negative_zero = left == SIGN and right == (0 if subtract else SIGN)
                    summed = nearest(value(left)+rhs, both_negative_zero)
                    components.append(nearest(value(summed)*coefficient, summed == SIGN))
                out[dest] = tuple(components)
    else:
        for i, pair in enumerate(state):
            if op == "z":
                out[i] = tuple((x+SIGN) % (2*SIGN) for x in pair) if i & flag else pair
            else:
                flip = flag if op == "x" else (1 << wires[1] if i & flag else 0)
                out[i ^ flip] = pair
    return out
