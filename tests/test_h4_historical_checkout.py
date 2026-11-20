"""Gate 4a: historical replay does not depend on the mutable current H4 engine."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools.high_support import h4_historical_checkout as history

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/h4-candidate/source.json"
RECEIPT = ROOT / "evidence/h4-candidate/receipt.json"


class HistoricalCheckoutReplay(unittest.TestCase):
    def test_accepted_v1_replays_with_historical_code(self):
        self.assertEqual(history.ACCEPTED_COMMIT,
                         "1726b96a4fecf63dbec052bd0192e2741f1e653f")
        result = history.verify(SOURCE, RECEIPT)
        self.assertEqual(result, ("VERIFIED_PASS", 0))

    def test_pinned_archive_snapshot_rejects_mutated_module_or_fixture(self):
        data = history.historical_archive()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            history.extract_pinned(data, root)
            history.validate_snapshot(root)
            for relpath in ("tools/high_support/h4_replay.py",
                            "tools/high_support/h4_candidate.py",
                            "evidence/h4-candidate/receipt.json"):
                with self.subTest(path=relpath):
                    file = root / relpath
                    old = file.read_bytes()
                    file.write_bytes(old + b"\n")
                    with self.assertRaisesRegex(ValueError, "content mismatch"):
                        history.validate_snapshot(root)
                    file.write_bytes(old)
                    history.validate_snapshot(root)

    def test_historical_replay_rejects_adversarial_input_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, receipt = root/"source.json", root/"receipt.json"
            source.write_bytes(SOURCE.read_bytes())
            original_receipt = RECEIPT.read_bytes()
            receipt.write_bytes(original_receipt)
            self.assertEqual(history.verify(source, receipt), ("VERIFIED_PASS", 0))
            tampered = json.loads(original_receipt)
            tampered["ledger"]["steps"][0]["total"] = "0"
            receipt.write_text(json.dumps(tampered, sort_keys=True,
                                          separators=(",", ":")) + "\n", encoding="utf-8")
            self.assertEqual(history.verify(source, receipt), ("INVALID_RECORD", 2))
            receipt.write_bytes(original_receipt)
            changed = json.loads(source.read_text(encoding="utf-8"))
            changed["budget"] = "0"
            source.write_text(json.dumps(changed, sort_keys=True,
                                         separators=(",", ":")) + "\n", encoding="utf-8")
            self.assertEqual(history.verify(source, receipt), ("INVALID_RECORD", 2))

    def test_current_candidate_module_is_not_required_for_historical_replay(self):
        # Simulated import-level drift. Historical CLI is spawned from the pinned tree.
        with mock.patch.dict(sys.modules, {
            "tools.high_support.h4_candidate": None,
            "tools.high_support.h4_candidate_archive": None,
        }):
            self.assertEqual(history.verify(SOURCE, RECEIPT), ("VERIFIED_PASS", 0))

    def test_unknown_or_missing_historical_git_version_fails_closed(self):
        with mock.patch.object(history, "ACCEPTED_COMMIT", "f"*40):
            with self.assertRaises(history.HistoryUnavailable):
                history.historical_archive()

    def test_historical_budget_exceeded_is_not_a_pass(self):
        # Produce a valid zero-budget receipt with the accepted *historical*
        # generator, not with the mutable current H4 engine.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            history.extract_pinned(history.historical_archive(), root)
            source = root / "zero-source.json"
            receipt = root / "zero-receipt.json"
            request = json.loads(SOURCE.read_bytes())
            request["budget"] = "0"
            source.write_text(json.dumps(request, sort_keys=True,
                                         separators=(",", ":")) + "\n", encoding="utf-8")
            flags = ["-" + "O"*sys.flags.optimize] if sys.flags.optimize else []
            command = [sys.executable, "-B", *flags, "-m",
                       "tools.high_support.h4_candidate", "generate",
                       str(source), str(receipt)]
            generated = subprocess.run(command, cwd=root,
                                       env=history.historical_environment(),
                                       capture_output=True, text=True, timeout=55)
            self.assertEqual(generated.returncode, 1, generated.stderr)
            self.assertEqual(generated.stdout.strip(), "VERIFIED_BUDGET_EXCEEDED")
            self.assertEqual(history.verify(source, receipt),
                             ("VERIFIED_BUDGET_EXCEEDED", 1))
            self.assertEqual(SOURCE.read_bytes()[-1:], b"\n")

    def test_cli_preserves_outcome_exit_status(self):
        flags = ["-" + "O"*sys.flags.optimize] if sys.flags.optimize else []
        command = [sys.executable, "-B", *flags, "-m",
                   "tools.high_support.h4_historical_checkout",
                   "verify", str(SOURCE), str(RECEIPT)]
        process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                 text=True, timeout=70)
        self.assertEqual((process.returncode, process.stdout.strip()),
                         (0, "VERIFIED_PASS"), process.stderr)


if __name__ == "__main__":
    unittest.main()
