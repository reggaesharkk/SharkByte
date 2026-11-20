"""Hostile worker replay checks for H4 outcome categories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/h3/circuit.json"
ARCHIVE = ROOT / "evidence/h4-gate1/windows-arm64.json"


class H4WorkerReplay(unittest.TestCase):
    def invoke(self, source, path, *flags):
        command = [sys.executable, "-B"]
        if sys.flags.optimize:
            command += ["-" + "O" * sys.flags.optimize]
        return subprocess.run(command + ["-m", "tools.high_support.h4_run", str(source),
                                         str(path), *flags], cwd=ROOT, capture_output=True,
                              text=True, timeout=65)

    def test_complete_receipt_default_and_explicit_ledger(self):
        receipt = json.loads(ARCHIVE.read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            receipt["verify"]["decision"] = "FAIL"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            result = self.invoke(SOURCE, path, "--replay")
            self.assertEqual((result.returncode, result.stdout.strip()), (2, "INVALID_RECORD"))
            path.write_text(json.dumps(receipt["ledger"]), encoding="utf-8")
            result = self.invoke(SOURCE, path, "--ledger-only")
            self.assertEqual((result.returncode, result.stdout.strip()), (0, "VERIFIED_PASS"))
            result = self.invoke(SOURCE, path, "--replay")
            self.assertEqual((result.returncode, result.stdout.strip()), (2, "INVALID_RECORD"))

    def test_budget_outcome_roundtrip(self):
        source = json.loads(SOURCE.read_bytes())
        source["budget"] = "0"
        with tempfile.TemporaryDirectory() as temp:
            src, path = Path(temp) / "source.json", Path(temp) / "receipt.json"
            src.write_text(json.dumps(source), encoding="utf-8")
            for flags in ((), ("--replay",)):
                result = self.invoke(src, path, *flags)
                self.assertEqual((result.returncode, result.stdout.strip()),
                                 (1, "VERIFIED_BUDGET_EXCEEDED"), result.stderr)
                self.assertTrue(path.is_file(), "valid exceeded-budget receipt must remain published")

    def test_unsupported_gate_publishes_nothing(self):
        source = json.loads(SOURCE.read_bytes())
        source["gates"][0][0] = "rx"
        with tempfile.TemporaryDirectory() as temp:
            src, path = Path(temp) / "source.json", Path(temp) / "receipt.json"
            src.write_text(json.dumps(source), encoding="utf-8")
            result = self.invoke(src, path)
            self.assertEqual((result.returncode, result.stdout.strip()), (3, "UNSUPPORTED"))
            self.assertFalse(path.exists())
