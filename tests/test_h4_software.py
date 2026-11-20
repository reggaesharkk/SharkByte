import copy
from fractions import Fraction as Q
import json
from pathlib import Path
import random
import unittest

from tools.high_support import h4_bits as bits, h4_replay as replay
from tools.high_support.h4_ledger import generate, strict_json, verify

ARCHIVE = Path(__file__).resolve().parents[1]/"evidence/h3"
SOURCE = (ARCHIVE/"circuit.json").read_text(encoding="utf-8")


def circuit(gates, state, budget="4"):
    return json.dumps({"qubits": 2, "initial": state, "gates": gates, "budget": budget})


class SoftwareBinary64(unittest.TestCase):
    def test_rounding_boundaries_and_signed_zero(self):
        for numerator, shift, expected in [
                (1, 1, 0), (3, 1, 2), (5, 1, 2),
                (2**53-1, 1, 2**52), (2**53+1, 1, 2**52),
                (2**53+3, 1, 2**52+2)]:
            for negative in (False, True):
                sign = bits.SIGN if negative else 0
                x = Q(numerator, 2**(1074+shift))
                self.assertEqual(bits.pack(numerator, shift, negative), sign | expected)
                self.assertEqual(replay.nearest(-x if negative else x), sign | expected)
        self.assertEqual(bits.add(bits.SIGN, bits.SIGN), bits.SIGN)
        self.assertEqual(bits.add(bits.SIGN, 0), 0)
        self.assertEqual(bits.add(1, bits.SIGN | 1), 0)
        self.assertEqual(bits.multiply(bits.SIGN), bits.SIGN)
        overflow_midpoint = bits.units(bits.MAX_FINITE) + 2**2044
        self.assertEqual(bits.pack(overflow_midpoint-1, 0, False), bits.MAX_FINITE)
        with self.assertRaisesRegex(ValueError, "overflow"):
            bits.pack(overflow_midpoint, 0, False)
        with self.assertRaisesRegex(ValueError, "overflow"):
            replay.nearest(Q(overflow_midpoint, 2**1074))

    def test_differential_operations(self):
        rng = random.Random(41)
        edge = [0, bits.SIGN, 1, bits.SIGN|1, 2**52-1, 2**52,
                bits.MAX_FINITE, bits.SIGN|bits.MAX_FINITE]
        for _ in range(200):
            state = [tuple(rng.choice(edge) if rng.randrange(3) == 0 else
                           rng.randrange(bits.MAX_FINITE+1) | rng.choice((0,bits.SIGN))
                           for _ in range(2)) for _ in range(2)]
            try:
                expected = replay.step(state, "h", [0])
            except ValueError:
                with self.assertRaisesRegex(ValueError, "overflow"):
                    bits.step(state, "h", [0])
            else:
                self.assertEqual(bits.step(state, "h", [0]), expected)

    def test_archived_native_comparison_and_forgery(self):
        ledger = generate(SOURCE)
        self.assertEqual(verify(SOURCE, ledger), "PASS")
        differences = 0
        for name in ("windows-arm64.json", "ubuntu-wsl2-arm64.json"):
            native = json.loads((ARCHIVE/name).read_text())["ledger"]
            for old, new in zip(native["steps"], ledger["steps"]):
                self.assertEqual({i: p for i,p in enumerate(new["post_bits"])
                                  if any(replay.value(int(w,16)) for w in p)}.keys(),
                                 {i for i,_,_ in old["post"]})
                for i, a, b in old["post"]:
                    pair = new["post_bits"][i]
                    self.assertEqual(list(map(lambda w: replay.value(int(w,16)), pair)),
                                     [replay.value(int(a,16)), replay.value(int(b,16))])
                    differences += sum(x != y for x,y in zip(pair,(a,b)))
                for key in ("arithmetic", "deleted_mass", "deletion", "total"):
                    self.assertEqual(old[key], new[key])
        self.assertGreater(differences, 0)
        for key, item in (("post_bits", [["xyz", "0"]]), ("arithmetic", "0"),
                          ("deletion", "1"), ("total", "0")):
            forged = copy.deepcopy(ledger)
            forged["steps"][0][key] = item
            with self.assertRaises(ValueError):
                verify(SOURCE, forged)
        forged = copy.deepcopy(ledger)
        word = int(forged["steps"][0]["post_bits"][7][0],16)
        forged["steps"][0]["post_bits"][7][0] = f"{word ^ bits.SIGN:016x}"
        with self.assertRaises(ValueError):
            verify(SOURCE, forged)
        with self.assertRaises(ValueError):
            verify(SOURCE+"\n", ledger)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            strict_json('{"a":1,"a":2}')

    def test_repeated_gates_deletions_and_refusals(self):
        initial = [[0,"3fe0000000000000","bfe0000000000000"],
                   [2,"8000000000000001","8000000000000000"]]
        h = ["h",[0],[]]
        sequence = [h, ["cx",[0,1],[]], ["z",[1],[]], ["x",[1],[]]]
        sequence += [h]*56 + [["h",[0],[0]],["h",[0],[1]]]
        src = circuit(sequence, initial)
        ledger = generate(src)
        self.assertEqual(verify(src, ledger), "PASS")
        self.assertTrue(all(Q(step["deleted_mass"]) > 0 for step in ledger["steps"][-2:]))
        self.assertEqual(verify(circuit([h], initial, "0"),
                                generate(circuit([h], initial, "0"))), "FAIL")
        with self.assertRaisesRegex(ValueError, "gate limit"):
            generate(circuit([h]*65, initial))
        with self.assertRaisesRegex(ValueError, "deadline"):
            generate(src, seconds=0)
        with self.assertRaisesRegex(ValueError, "overflow"):
            generate(circuit([h], [[i, "7fefffffffffffff", "0"*16] for i in (0,1)]))
