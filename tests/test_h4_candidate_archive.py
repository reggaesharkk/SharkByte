"""Hostile archival verification for frozen candidate-v1 without widening the public API."""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.high_support import h4_candidate as active_candidate
from tools.high_support import h4_candidate_archive as archive
from tools.high_support import h4_ledger

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/h4-candidate/source.json"
RECEIPT = ROOT / "evidence/h4-candidate/receipt.json"
PINNED_SOURCE_SHA = "9bda8fe9794ea6af6ab431ee1c6b81ccf8ad792ef1f11f5668ff7568bb761d59"


def zero_budget_record():
    source = json.loads(SOURCE.read_bytes())
    source["budget"] = "0"
    encoded = archive.canonical(source)
    ledger = h4_ledger.generate(archive.translate_v1(encoded))
    record = archive.canonical({
        "contract": archive.CONTRACT,
        "source_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "candidate_sha256": archive.ARCHIVED_CANDIDATE_SHA256,
        "ledger": ledger,
        "outcome": "VERIFIED_BUDGET_EXCEEDED",
    })
    return encoded, record


class ArchiveV1(unittest.TestCase):
    def test_fixture_and_frozen_contract(self):
        source, receipt = SOURCE.read_text(encoding="utf-8"), RECEIPT.read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), PINNED_SOURCE_SHA)
        self.assertEqual(archive.ARCHIVED_COMMIT,
                         "1726b96a4fecf63dbec052bd0192e2741f1e653f")
        self.assertEqual(archive.verify(source, receipt), "VERIFIED_PASS")
        self.assertEqual(archive.translate_v1(source), active_candidate.translate(source))
        self.assertEqual(json.loads(receipt)["ledger"]["modules"], archive.ARCHIVED_H4_MODULES)
        self.assertEqual(archive.canonical(json.loads(receipt)), receipt)

    def test_future_candidate_script_change_does_not_change_archive_decoder(self):
        source, receipt = SOURCE.read_text(), RECEIPT.read_text()
        # Simulates a future candidate script with a new exact self-hash.
        fake_binding = dict(active_candidate.binding(source), candidate_sha256="0"*64)
        with mock.patch.object(active_candidate, "binding", return_value=fake_binding):
            with self.assertRaises(ValueError):
                active_candidate.verify(source, receipt)
            self.assertEqual(archive.verify(source, receipt), "VERIFIED_PASS")

    def test_unregistered_candidate_and_module_mix_fail_closed(self):
        source = SOURCE.read_text()
        receipt = json.loads(RECEIPT.read_text())
        for patch in (
            {"candidate_sha256": "0"*64},
            {"candidate_sha256": "6f2d5a700f553e9a3c0fab0eb4e64ff1c20fd7872523f0acfd24ab6439189a68"},
            {"contract": "sharkbyte-xz-cx-h-candidate-v2"},
            {"source_sha256": "f"*64},
            {"outcome": "VERIFIED_BUDGET_EXCEEDED"},
        ):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    archive.verify(source, archive.canonical(dict(receipt, **patch)))
        for module in ("h4_bits.py", "h4_ledger.py", "h4_run.py"):
            with self.subTest(module=module):
                modified = json.loads(RECEIPT.read_text())
                modified["ledger"]["modules"][module] = "0"*64
                with self.assertRaises(ValueError):
                    archive.verify(source, archive.canonical(modified))
        modified = json.loads(RECEIPT.read_text())
        modified["ledger"]["modules"]["injected.py"] = "0"*64
        with self.assertRaises(ValueError):
            archive.verify(source, archive.canonical(modified))

    def test_no_self_reported_hash_can_override_mathematical_replay(self):
        source = SOURCE.read_text()
        record = json.loads(RECEIPT.read_text())
        record["ledger"]["steps"][0]["total"] = "0"
        with self.assertRaises(ValueError):
            archive.verify(source, archive.canonical(record))
        record = json.loads(RECEIPT.read_text())
        record["ledger"]["steps"][0]["post_bits"][0][0] = "0000000000000000"
        with self.assertRaises(ValueError):
            archive.verify(source, archive.canonical(record))
        tampered_source = json.loads(source)
        tampered_source["gates"].reverse()
        with self.assertRaises(ValueError):
            archive.verify(archive.canonical(tampered_source), RECEIPT.read_text())

    def test_strict_source_canonicalization_and_contract(self):
        source = SOURCE.read_text()
        for malformed in (source.rstrip(), source+" ", source.replace('"budget":', '"budget":"1","budget":'),
                          source.replace('"budget":"1"', '"budget":"2/2"')):
            with self.subTest(kind=malformed[:40]):
                with self.assertRaises(ValueError):
                    archive.translate_v1(malformed)
        request = json.loads(source)
        request["gates"][0].append([0])
        with self.assertRaises(ValueError):
            archive.translate_v1(archive.canonical(request))
        request = json.loads(source)
        request["initial"].reverse()
        with self.assertRaises(ValueError):
            archive.translate_v1(archive.canonical(request))
        request = json.loads(source)
        request["contract"] = "sharkbyte-xz-cx-h-candidate-v2"
        with self.assertRaises(h4_ledger.UnsupportedOperation):
            archive.translate_v1(archive.canonical(request))

    def test_verified_budget_excess_is_not_an_accuracy_pass(self):
        source, record = zero_budget_record()
        self.assertEqual(archive.verify(source, record), "VERIFIED_BUDGET_EXCEEDED")
        data = json.loads(record)
        self.assertEqual(data["ledger"]["decision"], "FAIL")
        self.assertEqual(archive.EXIT[archive.verify(source, record)], 1)

    def test_bounded_cli_outcome_codes_no_publication(self):
        archived_bytes = RECEIPT.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            src, receipt = Path(folder)/"source.json", Path(folder)/"receipt.json"
            src.write_bytes(SOURCE.read_bytes())
            receipt.write_bytes(archived_bytes)
            command = [sys.executable, "-B"]
            if sys.flags.optimize:
                command.append("-"+"O"*sys.flags.optimize)
            command.extend(["-m", archive.MODULE, "verify"])

            def check(outcome):
                result = subprocess.run(command+[str(src), str(receipt)], cwd=ROOT,
                                        capture_output=True, text=True, timeout=55)
                self.assertEqual((result.returncode, result.stdout.strip()),
                                 (archive.EXIT[outcome], outcome), result.stderr)

            check("VERIFIED_PASS")
            zero_source, zero_record = zero_budget_record()
            src.write_text(zero_source, encoding="utf-8")
            receipt.write_text(zero_record, encoding="utf-8")
            check("VERIFIED_BUDGET_EXCEEDED")
            receipt.write_text(archive.canonical(dict(json.loads(zero_record), candidate_sha256="f"*64)))
            check("INVALID_RECORD")
            req = json.loads(zero_source)
            req["contract"] = "sharkbyte-xz-cx-h-candidate-v2"
            src.write_text(archive.canonical(req))
            check("UNSUPPORTED")
            self.assertEqual(RECEIPT.read_bytes(), archived_bytes,
                             "archival verifier must not edit historical receipts")


if __name__ == "__main__":
    unittest.main()
