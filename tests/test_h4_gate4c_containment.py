"""Gate 4c policy, input and child-process integration tests.

These checks do not assert that the historical candidate proves public H support.
"""
import json
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
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
        for raw in (b'{"exit_code":2,"exit_code":0,"report":{"decision":"COMPATIBLE"}}\n',
                    b'{"exit_code":0,"report":{"decision":"COMPATIBLE","x":NaN}}\n'):
            with self.assertRaises(c.ContainmentUnavailable):
                c._check_child_result(raw)

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
        self.assertEqual(list(report["input_sha256"].values()),
                         [hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (SOURCE, RECEIPT, SOURCE, RECEIPT)])
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

    def test_oversized_receipt_and_malformed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"bad"
            path.write_bytes(b"x"*(c.history.RECEIPT_LIMIT+1))
            with patch.object(c, "_windows_launch", side_effect=AssertionError("launched")), \
                 patch.object(c, "_linux_launch", side_effect=AssertionError("launched")):
                self.assertEqual(c.supervise(args(receipt=path))[1], 2)
            path.write_bytes(SOURCE.read_bytes()+b"\n")
            self.assertEqual(c.supervise(args(source=path))[1], 2)

    def test_valid_non_equivalent_budget(self):
        from tools.high_support import h4_compatibility as v1
        with tempfile.TemporaryDirectory() as temp:
            src, cert = (Path(temp)/name for name in ("source","receipt"))
            source = c._canonical(dict(json.loads(SOURCE.read_bytes()), budget="0")).encode()
            _, record = v1.reconstruct(source)
            src.write_bytes(source)
            cert.write_bytes(c._canonical(record).encode())
            report, code = c.supervise(args()[:3] + args(src, cert)[3:])
            self.assertEqual((code,report["decision"]), (1,"NOT_ESTABLISHED"), report)
            self.assertEqual(report["within_budget_certified"], [True,False])


@unittest.skipUnless(platform.system() in ("Windows", "Linux"), "supported supervisor")
class NativeContainment(unittest.TestCase):
    @staticmethod
    def launch(script, working_dir, *, seconds=8, mib=64, arguments=()):
        launch = c._windows_launch if os.name == "nt" else c._linux_launch
        return launch([sys.executable, "-B", "-c", script, *arguments],
                      time.monotonic()+seconds, mib*1024**2, working_dir)

    def test_real_memory_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root/"refused"
            script = ("import pathlib,sys\ntry:\n bytearray(96*1024**2)\n"
                      "except MemoryError:\n pathlib.Path(sys.argv[1]).write_text('refused')\n"
                      "else:\n raise SystemExit(7)\n")
            try:
                report = self.launch(script, root, arguments=(str(marker),))
            except c.ContainmentUnavailable as exc:
                # An adversarial allocation can be refused while the Windows
                # reported peak exceeds the cap. Do not accept such a run.
                if os.name != "nt":
                    raise
                self.assertIn("outer job commit telemetry exceeded cap", str(exc))
            else:
                self.assertEqual(report["active_after_cleanup"], 0)
            self.assertEqual(marker.read_text(), "refused")

    def test_started_worker_deadline_kills_descendant(self):
        self.check_descendant(timeout=True)

    def test_worker_exit_drains_descendant(self):
        self.check_descendant(timeout=False)

    def check_descendant(self, *, timeout):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root/"pid"
            script = ("import pathlib,subprocess,sys,time\n"
                      "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
                      "pathlib.Path(sys.argv[1]).write_text(str(p.pid))\n"
                      "if sys.argv[2]=='True': time.sleep(30)\n")
            arguments = (str(marker),str(timeout))
            if timeout or os.name == "nt":
                # Windows refuses a completed worker with surviving children.
                with self.assertRaises((TimeoutError,RuntimeError)):
                    self.launch(script,root,seconds=3,arguments=arguments)
            else:
                self.assertEqual(self.launch(script,root,arguments=arguments)["active_after_cleanup"],0)
            child = int(marker.read_text())
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                kernel = ctypes.WinDLL("kernel32",use_last_error=True)
                kernel.OpenProcess.argtypes = (wintypes.DWORD,wintypes.BOOL,wintypes.DWORD)
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE,wintypes.DWORD)
                kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
                handle = kernel.OpenProcess(0x100000,False,child)
                if handle:
                    try:
                        # Job accounting can reach zero just before the process
                        # object signals. Require bounded termination, not a
                        # particular ordering of Windows notifications.
                        self.assertEqual(kernel.WaitForSingleObject(handle,2000),0)
                    finally:
                        kernel.CloseHandle(handle)
                else:
                    self.assertEqual(ctypes.get_last_error(),87)
            else:
                entry = Path(f"/proc/{child}/stat")
                try:
                    state = entry.read_bytes().rsplit(b")",1)[1].split()[0]
                except FileNotFoundError:
                    return
                self.assertIn(state,(b"Z",b"X"))


if __name__ == "__main__":
    unittest.main()
