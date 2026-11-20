import json
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.high_support import h4_candidate as c

ROOT = Path(__file__).resolve().parents[1]


def source(budget=Fraction(1)):
    return c.encode_source(2, [["h", [0]], ["cx", [0, 1]], ["z", [1]], ["h", [0]]],
                           {0: (1., -0.), 2: (-0., float.fromhex("0x0.0000000000001p-1022"))},
                           budget)


class Candidate(unittest.TestCase):
    def test_canonical_conversion(self):
        self.assertEqual(c.binary64_word(-0.), "8000000000000000")
        self.assertEqual(c.binary64_word(float.fromhex("0x0.0000000000001p-1022")), "0000000000000001")
        self.assertEqual(c.binary64_word(sys.float_info.max), "7fefffffffffffff")
        for value in (1, True, "1", float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                c.binary64_word(value)
        original = source()
        data = json.loads(original)
        self.assertEqual(data["initial"][0][-1], "8000000000000000")
        for key, value in (("budget", "2/2"), ("initial", data["initial"][::-1]),
                           ("gates", [["h", [0], [1]]]), ("qubits", True)):
            with self.assertRaises(ValueError):
                c.translate(c.canonical(dict(data, **{key: value})))
        for bad in (original.strip(), original.replace('"budget":', '"budget":"1","budget":')):
            with self.assertRaises(ValueError):
                c.translate(bad)

    def test_independent_replay_and_tampering(self):
        text = source()
        record = c.generate(text)
        self.assertEqual(c.verify(text, record), "VERIFIED_PASS")
        self.assertEqual(record, c.generate(text))
        for field, value in (("arithmetic", "0"), ("deletion", "1"),
                             ("post_bits", [["0"*16]*2]), ("total", "0")):
            bad = json.loads(record)
            bad["ledger"]["steps"][0][field] = value
            with self.assertRaises(ValueError):
                c.verify(text, c.canonical(bad))
        for key, value in (("outcome", "VERIFIED_BUDGET_EXCEEDED"), ("contract", "v2")):
            with self.assertRaises(ValueError):
                c.verify(text, c.canonical(dict(json.loads(record), **{key: value})))
        changed = json.loads(text)
        changed["initial"][0][2] = "0000000000000000"
        with self.assertRaises(ValueError):
            c.verify(c.canonical(changed), record)
        with self.assertRaises(ValueError):
            c.verify(text, record.rstrip())
        with self.assertRaises(ValueError):
            c.verify(text, " "*(c.LIMIT+1))

    def test_bounds_and_overflow(self):
        with self.assertRaises(ValueError):
            c.encode_source(9, [], {}, Fraction(0))
        with self.assertRaises(ValueError):
            c.encode_source(1, [["h", [0]]]*65, {}, Fraction(0))
        with self.assertRaisesRegex(ValueError, "overflow"):
            c.generate(c.encode_source(1, [["h", [0]]],
                                       {i: (sys.float_info.max, 0.) for i in (0, 1)}, Fraction(1)))

    def test_cli_exit_contract_and_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            request = Path(temp)/"request.json"
            receipt = Path(temp)/"receipt.json"
            cmd = [sys.executable, "-B"]
            if sys.flags.optimize:
                cmd.append("-" + "O"*sys.flags.optimize)
            cmd += ["-m", c.MODULE]

            def check(mode, outcome):
                result = subprocess.run(cmd+[mode, str(request), str(receipt)], cwd=ROOT,
                                        capture_output=True, text=True, timeout=65)
                self.assertEqual((result.returncode, result.stdout.strip()),
                                 (c.EXIT[outcome], outcome), result.stderr)

            request.write_bytes(source(Fraction(0)).encode())
            check("generate", "VERIFIED_BUDGET_EXCEEDED")
            check("verify", "VERIFIED_BUDGET_EXCEEDED")
            original = receipt.read_bytes()
            check("generate", "INVALID_RECORD")
            self.assertEqual(receipt.read_bytes(), original)
            unknown = json.loads(source())
            unknown["gates"][0][0] = "rx"
            request.write_bytes(c.canonical(unknown).encode())
            receipt.unlink()
            check("generate", "UNSUPPORTED")
            self.assertFalse(receipt.exists())
            request.write_bytes(b" "*(c.SOURCE_LIMIT+1))
            check("generate", "INVALID_RECORD")
            self.assertFalse(receipt.exists())
