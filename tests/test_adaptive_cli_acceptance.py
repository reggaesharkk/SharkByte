"""Integrity and scope regressions for archived adaptive CLI receipts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_adaptive_cli_acceptance import CASES, verify_record

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "adaptive-cli-cross-platform-20261118"


class AdaptiveCliAcceptanceReceiptTests(unittest.TestCase):
    def test_all_six_original_receipts_match_their_fixtures(self):
        record_hashes = {}
        for host in ("windows-arm64", "ubuntu-wsl2-arm64"):
            for case, expected in CASES.items():
                verified = verify_record(EVIDENCE / host / f"{case}.json", case, expected)
                record_hashes.setdefault(case, set()).add(verified["record_sha256"])
        self.assertTrue(all(len(hashes) == 1 for hashes in record_hashes.values()))

    def test_modified_result_without_resealing_is_rejected(self):
        original = EVIDENCE / "windows-arm64" / "ghz20-completed.json"
        record = json.loads(original.read_text(encoding="utf-8"))
        record["result"]["status"] = "RESOURCE_STOP"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tampered.json"
            path.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "record digest mismatch"):
                verify_record(path, "ghz20-completed", CASES["ghz20-completed"])

    def test_random_case_contracts_are_explicit(self):
        dense = CASES["random-connected20-dense-switch"]
        stopped = CASES["random-connected20-resource-stop"]
        self.assertEqual(dense["transition"]["gate_index"], 16)
        self.assertEqual(dense["transition"]["support"], 65536)
        self.assertEqual(stopped["gate_index"], 10)
        self.assertEqual(stopped["exit"], 1)


if __name__ == "__main__":
    unittest.main()
