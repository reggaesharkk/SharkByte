import copy
import json
import math
from pathlib import Path
import random
import sys
import unittest
from fractions import Fraction

from tools.high_support.h3_format import encode
from tools.high_support.h3_generate import generate
from tools.high_support.h3_verify import verify

FIXTURE = Path(__file__).resolve().parents[1]/"evidence/h3/circuit.json"


def source(gates, initial=None, budget="1", qubits=3):
    return json.dumps(dict(qubits=qubits, initial=encode({0: 1j} if initial is None else initial),
                           gates=gates, budget=budget))


class CumulativeHadamard(unittest.TestCase):
    def test_fixture_and_coherent_accumulation(self):
        fixture = FIXTURE.read_bytes().decode()
        self.assertEqual(verify(fixture, generate(fixture)), "PASS")
        repeated = source([["h", [0], []]]*64)
        ledger = generate(repeated)
        self.assertEqual(verify(repeated, ledger), "PASS")
        self.assertNotEqual(ledger["steps"][1]["post"], ledger["steps"][63]["post"])

    def test_seeded_prefixes(self):
        rng = random.Random(328)
        for _ in range(20):
            gates = []
            for _ in range(24):
                op = rng.choice(("h", "h", "x", "z", "cx"))
                wires = rng.sample(range(3), 2 if op == "cx" else 1)
                delete = rng.sample(range(8), rng.randrange(2))
                gates.append([op, wires, delete])
            circuit = source(gates, {0: .125-.25j, 3: complex(0., math.ulp(0.))}, "4")
            self.assertEqual(verify(circuit, generate(circuit)), "PASS")

    def test_two_nonzero_deletions_and_actual_input_norm(self):
        circuit = source([["h", [0], [1]], ["h", [0], [1]]],
                         {0: complex(.5, -.5)}, "1")
        ledger = generate(circuit)
        first, second = ledger["steps"]
        self.assertGreater(Fraction(first["deleted_mass"]), 0)
        self.assertGreater(Fraction(second["deleted_mass"]), 0)
        self.assertLess(Fraction(second["norm_upper"]), Fraction(first["norm_upper"]))
        self.assertEqual(verify(circuit, ledger), "PASS")

    def test_forged_ledger(self):
        circuit = source([["h",[0],[]], ["h",[1],[1]]])
        genuine = generate(circuit)
        for name, value in [("post", []), ("arithmetic", "0"), ("pairs", 0),
                            ("deleted_mass", "1"), ("norm_upper", "0"), ("total", "0")]:
            forged = copy.deepcopy(genuine)
            forged["steps"][0][name] = value
            with self.assertRaises(ValueError):
                verify(circuit, forged)
        for key, value in [("coefficient_bits", "0"*16), ("steps", []), ("decision", "FAIL")]:
            with self.assertRaises(ValueError):
                verify(circuit, dict(genuine, **{key: value}))
        with self.assertRaises(ValueError):
            verify(source([["h",[1],[1]], ["h",[0],[]]]), genuine)

    def test_budget_overflow_and_limits(self):
        h = ["h", [0], []]
        circuit = source([h], {0: complex(math.ulp(0.))}, "0")
        ledger = generate(circuit)
        self.assertNotEqual(ledger["steps"][0]["arithmetic"], "0")
        self.assertEqual(verify(circuit, ledger), "FAIL")
        overflow = .6*sys.float_info.max
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            generate(source([h], {0: complex(overflow), 1: complex(overflow)}))
        with self.assertRaises(ValueError):
            generate(source([h], {0: complex(float("inf"))}))
        with self.assertRaises(ValueError):
            generate(source([h]*65))
        with self.assertRaisesRegex(ValueError, "deadline"):
            generate(circuit, seconds=0)
        with self.assertRaisesRegex(ValueError, "deadline"):
            verify(circuit, ledger, seconds=0)
