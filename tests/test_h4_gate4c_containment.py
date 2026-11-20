"""Gate 4c policy, input and child-process integration tests.

These checks do not assert that the historical candidate proves public H support.
"""
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.high_support import h4_compatibility_contained as c

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/h4-candidate/source.json"
RECEIPT = ROOT / "evidence/h4-candidate/receipt.json"
VERSION = "sharkbyte-xz-cx-h-candidate-v1"


def args(source=SOURCE, receipt=RECEIPT, version=VERSION):
    return [version, str(source), str(receipt), version, str(source), str(receipt)]


class Gate4c(unittest.TestCase):
    def test_category_parser_fail_closed(self):
        for code, label in c.DECISIONS.items():
            payload = {"exit_code": code, "report": {"decision": label}}
            self.assertEqual(c._check_child_result(c._canonical(payload).encode())["exit_code"], code)
            for tampered in (
                {"exit_code": code, "report": {"decision": "NOT_A_RESULT"}},
                {"exit_code": True, "report": {"decision": label}},
                {"exit_code": code, "report": {"decision": label}, "extra": 1},
            ):
                with self.assertRaises(c.ContainmentUnavailable):
                    c._check_child_result(c._canonical(tampered).encode())
        with self.assertRaises(c.ContainmentUnavailable):
            c._check_child_result(b"x" * (c.MAX_RESULT_BYTES + 1))

    def test_bad_parameters_rejected_before_worker(self):
        for memory, seconds in [(0, 10), (31, 10), (1025, 10),
                                (256, 0), (256, -1), (256, float("inf")),
                                (256, float("nan")), (256, 181)]:
            with self.assertRaises(ValueError):
                c.supervise(args(), memory_mib=memory, seconds=seconds)

    def test_invalid_large_input_no_worker_spawn(self):
        with tempfile.TemporaryDirectory() as temp:
            bad = Path(temp) / "oversized.json"
            bad.write_bytes(b"a" * (32768 + 1))
            with patch.object(c, "_windows_launch", side_effect=AssertionError("launched")), \
                 patch.object(c, "_linux_launch", side_effect=AssertionError("launched")):
                result, status = c.supervise(args(source=bad))
            self.assertEqual((result["decision"], status), ("INVALID_RECORD", 2))

    def test_refuse_nonregular_inputs_before_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "not-a-file"
            directory.mkdir()
            with patch.object(c, "_windows_launch", side_effect=AssertionError("launched")), \
                 patch.object(c, "_linux_launch", side_effect=AssertionError("launched")):
                report, code = c.supervise(args(source=directory))
            self.assertEqual((code, report["decision"]), (2, "INVALID_RECORD"))
            if hasattr(__import__("os"), "mkfifo"):
                pipe = Path(temp) / "pipe"
                __import__("os").mkfifo(pipe)
                with patch.object(c, "_linux_launch", side_effect=AssertionError("launched")):
                    report, code = c.supervise(args(source=pipe))
                self.assertEqual((code, report["decision"]), (2, "INVALID_RECORD"))

    def test_verified_identity_inside_os_worker(self):
        report, code = c.supervise(args(), seconds=90)
        self.assertEqual((code, report["decision"]), (0, "COMPATIBLE"), report)
        self.assertEqual(report["execution_authenticity"], "UNAUTHENTICATED")
        self.assertEqual(len(report["input_sha256"]), 4)
        self.assertIn(report["containment"]["os_limit"],
                      ("RLIMIT_AS_per_process", "Windows_JOB_OBJECT_LIMIT_JOB_MEMORY"))
        if platform.system() == "Windows":
            self.assertEqual(report["containment"]["active_after_cleanup"], 0)
            self.assertLessEqual(report["containment"]["peak_job_committed_bytes"],
                                 report["containment"]["limit_bytes"])

    def test_valid_version_but_mutated_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            record = json.loads(RECEIPT.read_text())
            record["candidate_sha256"] = "0" * 64
            path = Path(temp) / "forged.json"
            path.write_bytes((json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode())
            report, code = c.supervise(args(receipt=path), seconds=90)
        self.assertEqual((code, report["decision"]), (2, "INVALID_RECORD"), report)

    def test_unknown_version_is_unsupported(self):
        report, code = c.supervise(args(version="candidate-v2-UNREGISTERED"), seconds=90)
        self.assertEqual((code, report["decision"]), (3, "UNSUPPORTED"), report)

    def test_near_zero_deadline_refuses_without_publishing(self):
        report, code = c.supervise(args(), seconds=0.000001)
        self.assertEqual((code, report["decision"]), (3, "UNSUPPORTED"), report)

    def test_cli_returns_real_decision_code(self):
        cli = [sys.executable, "-B", "-m", c.MODULE, "--seconds", "90", *args()]
        run = subprocess.run(cli, cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        report = json.loads(run.stdout)
        self.assertEqual(report["decision"], "COMPATIBLE")
        self.assertNotIn("candidate-v2", report.get("registered_versions", []))

    def test_unreadable_input_rejected(self):
        missing = SOURCE.parent / "nonexistent_gate4c_source.json"
        report, code = c.supervise(args(source=missing))
        self.assertEqual((code, report["decision"]), (3, "UNSUPPORTED"), report)

    def test_child_runs_separately_from_parent(self):
        # The parent must not call the mathematical engine directly.
        with patch.object(c, "_decision", side_effect=AssertionError("parent replay")):
            report, code = c.supervise(args(), seconds=90)
        self.assertEqual((code, report["decision"]), (0, "COMPATIBLE"), report)


if __name__ == "__main__":
    unittest.main()
