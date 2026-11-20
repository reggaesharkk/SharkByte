"""Cross-platform H3 archival replay gate; does not enable public certification."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest

from tools.high_support.h3_format import decode, digest, rows, sources
from tools.high_support.h3_verify import verify


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence" / "h3"
SOURCE = ARCHIVE / "circuit.json"
RECEIPTS = ("windows-arm64.json", "ubuntu-wsl2-arm64.json")


def load_receipt(name):
    return json.loads((ARCHIVE / name).read_text(encoding="utf-8"))


def exact_state(entries):
    values = rows(entries, 1 << 3)
    return {i: (Fraction(z.real), Fraction(z.imag))
            for i, z in values.items() if z != 0j}


class ArchivedH3ReplayGate(unittest.TestCase):
    def test_original_archives_and_module_bindings(self):
        source = SOURCE.read_text(encoding="utf-8")
        for name in RECEIPTS:
            with self.subTest(receipt=name):
                receipt = load_receipt(name)
                ledger = receipt["ledger"]
                self.assertEqual(ledger["source_sha256"], digest(source))
                self.assertEqual(ledger["modules"], sources())
                self.assertEqual(ledger["decision"], "PASS")
                self.assertEqual(receipt["generate"]["decision"], "PASS")
                self.assertEqual(receipt["verify"]["decision"], "PASS")
                self.assertEqual(verify(source, ledger), "PASS")

    def test_cross_platform_exact_mathematical_agreement(self):
        windows = load_receipt(RECEIPTS[0])["ledger"]
        linux = load_receipt(RECEIPTS[1])["ledger"]
        for field in ("source_sha256", "modules", "coefficient_bits", "order",
                      "assumptions", "initial_norm_squared", "budget", "final", "decision"):
            with self.subTest(field=field):
                self.assertEqual(windows[field], linux[field])
        self.assertEqual(len(windows["steps"]), len(linux["steps"]))
        for i, (left, right) in enumerate(zip(windows["steps"], linux["steps"])):
            with self.subTest(gate=i):
                for key in ("norm_upper", "pairs", "arithmetic", "deleted_mass",
                            "deletion", "total"):
                    self.assertEqual(left[key], right[key])
                self.assertEqual(exact_state(left["post"]), exact_state(right["post"]))

    def test_source_and_ledger_tampering_fail_closed(self):
        source = SOURCE.read_text(encoding="utf-8")
        original = load_receipt(RECEIPTS[0])["ledger"]
        with self.assertRaises(ValueError):
            verify(source + "\n", original)
        cases = (
            ("source_sha256", lambda d: d.__setitem__("source_sha256", "0" * 64)),
            ("coefficient_bits", lambda d: d.__setitem__("coefficient_bits", "0" * 16)),
            ("missing_step", lambda d: d["steps"].pop()),
            ("forged_charge", lambda d: d["steps"][0].__setitem__("arithmetic", "0")),
            ("forged_pair_count", lambda d: d["steps"][0].__setitem__("pairs", 0)),
            ("forged_state", lambda d: d["steps"][0]["post"][0].__setitem__(
                1, format(int(d["steps"][0]["post"][0][1], 16) ^ 1, "016x"))),
            ("reordered_events", lambda d: d["steps"].__setitem__(
                slice(0, 2), [d["steps"][1], d["steps"][0]])),
        )
        for label, change in cases:
            with self.subTest(tamper=label):
                forged = copy.deepcopy(original)
                change(forged)
                with self.assertRaises(ValueError):
                    verify(source, forged)

    def test_signed_zero_is_mathematical_not_bit_exact_identity(self):
        source = SOURCE.read_text(encoding="utf-8")
        original = load_receipt(RECEIPTS[0])["ledger"]
        modified = copy.deepcopy(original)
        flipped = False
        for step in modified["steps"]:
            for entry in step["post"]:
                for coordinate in (1, 2):
                    value = entry[coordinate]
                    if value in ("0000000000000000", "8000000000000000"):
                        entry[coordinate] = ("8000000000000000"
                                             if value[0] == "0"
                                             else "0000000000000000")
                        flipped = True
                        break
                if flipped:
                    break
            if flipped:
                break
        self.assertTrue(flipped, "fixture must include a signed zero")
        self.assertEqual(verify(source, modified), "PASS")
        self.assertNotEqual(original["steps"], modified["steps"])


if __name__ == "__main__":
    unittest.main()
