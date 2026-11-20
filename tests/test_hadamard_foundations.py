import math
import random
import sys
import unittest
from fractions import Fraction

from tools.high_support.hadamard_foundations import bits, deletion_ticks, enclose, sign
from tools.high_support.replay_hadamard_foundations import verify


class HadamardFoundations(unittest.TestCase):
    def test_ticks_and_pell(self):
        self.assertEqual(deletion_ticks(0, 1, 1, Fraction(1, 100)), 119)
        self.assertEqual(deletion_ticks(4, 0, 9, Fraction(2, 3)), 1)
        self.assertEqual(deletion_ticks(0, 0, 1, Fraction(1)), 0)
        p, q = 1, 1
        for i in range(1, 151):
            self.assertEqual(p*p - 2*q*q, (-1)**i)
            self.assertEqual(sign(p, -q), (-1)**i)
            # The conjugate product gives the small positive residual exactly.
            # Its reciprocal lies strictly between p+q and p+2q.
            a, b = (-1)**i*p, -(-1)**i*q
            self.assertEqual(deletion_ticks(a, b, 1, Fraction(1)), 1)
            p, q = p + 2*q, p + q
        self.assertEqual(131836323 - 93222358*math.sqrt(2), 0)
        with self.assertRaises(ValueError):
            deletion_ticks(0, -1, 1, Fraction(1))

    def test_operation_and_ideal_enclosure(self):
        tiny = math.ulp(0.0)
        cases = [(complex(tiny, -tiny), 0j), (complex(-0., -0.), 0j),
                 (complex(sys.float_info.min, tiny), complex(-tiny, tiny)),
                 (complex(2.**900, -1), complex(-2.**900, 1))]
        rng = random.Random(25)
        for _ in range(128):
            coords = [math.ldexp(rng.uniform(-1, 1), rng.randint(-1074, 1000))
                      for _ in range(4)]
            cases.append((complex(*coords[:2]), complex(*coords[2:])))
        for low, high in cases:
            self.assertEqual(verify(enclose(low, high)), "PASS")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            enclose(complex(.6*sys.float_info.max), complex(.6*sys.float_info.max))
        forged = enclose(1j, 0j)
        forged["output_bits"][1] = bits(1.)
        with self.assertRaises(ValueError):
            verify(forged)

    def test_historical_counterexamples_and_zero_contracts(self):
        c = 1/math.sqrt(2)
        self.assertEqual((2*c*c).hex(), "0x1.ffffffffffffep-1")
        self.assertEqual(math.prod([c]*20).hex(), "0x1.ffffffffffff2p-11")
        self.assertNotEqual(bits(-0.), bits(0.))
        self.assertEqual(Fraction(-0.), Fraction(0.))
        tiny = Fraction(1, 2**1074)
        # sqrt(1/2) < 3/4, so the relative-only bound fails.
        self.assertGreater(tiny/4, 3*Fraction(1, 2**53)*tiny)
        self.assertEqual(math.ulp(0.) * c, math.ulp(0.))
