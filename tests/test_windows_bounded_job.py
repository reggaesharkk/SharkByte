"""Native Windows lifecycle regressions for the bounded-support supervisor."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == "nt","Win32 Job Object")
class JobTests(unittest.TestCase):
    def test_descendant_drained_on_failure(self):
        from tools.high_support.windows_job import Job
        job = Job(128<<20)
        report = {}
        script = ("import subprocess,sys; "
                  "subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],"
                  "creationflags=subprocess.CREATE_NO_WINDOW)")
        try:
            with self.assertRaisesRegex(RuntimeError,"descendants"):
                job.run(["-c",script],Path.cwd(),time.monotonic()+10,{})
        finally:
            job.finish(report)
        self.assertGreaterEqual(report["total_processes"],2)
        self.assertEqual(report["active_after_cleanup"],0)

    def test_last_handle_closes_suspended_worker(self):
        from tools.high_support.windows_job import Job, checked, close, wait
        job = Job(128<<20)
        worker = job.launch(["-c","pass"],Path.cwd())
        try:
            checked(close(job.handle))
            self.assertEqual(wait(worker.process,10000),0)
        finally:
            checked(close(worker.thread))
            checked(close(worker.process))

    def test_assignment_failure_prevents_execution(self):
        from tools.high_support import windows_job as win
        job = win.Job(128<<20)
        report = {}
        try:
            # Fail construction of the mandatory JOB_LIST attribute.
            with patch.object(win,"update",return_value=0), patch.object(win,"create") as create:
                with self.assertRaises(OSError):
                    job.run(["-c","pass"],Path.cwd(),time.monotonic()+10,{})
                create.assert_not_called()
        finally:
            job.finish(report)
        self.assertEqual(report["total_processes"],0)

    def test_invalid_receipt_and_existing_destination(self):
        from tools.high_support.limit_bounded_windows import ROOT, supervise
        source = ROOT/"examples/high_support/adaptive_sparse_ghz_20q.sbq"
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder)/"bad"
            bad.write_text("{}")
            output = Path(folder)/"report"
            result = supervise("verify",source,output,[str(bad)],128,10)
            self.assertEqual(result["status"],"worker_failed")
            self.assertFalse(output.exists())
            self.assertEqual(result["active_after_cleanup"],0)
            output.write_text("original")
            with self.assertRaises(FileExistsError):
                supervise("verify",source,output,[str(bad)],128,10)
            self.assertEqual(output.read_text(),"original")

    def test_publication_deadline_rolls_back_only_this_result(self):
        from tools.high_support.limit_bounded_windows import ROOT, Job, supervise
        original_run = Job.run

        def delayed_publisher(job,args,cwd,deadline,stage):
            if stage["phase"] == "publish":
                directory, destination = Path(args[3]), Path(args[-1])
                script = ("import os,sys,time; os.rename(sys.argv[1],sys.argv[2]);"
                          "time.sleep(10)")
                args = ["-c",script,directory/"completed",destination]
                deadline = min(deadline,time.monotonic()+0.5)
            return original_run(job,args,cwd,deadline,stage)

        with tempfile.TemporaryDirectory() as folder, patch.object(Job,"run",delayed_publisher):
            output = Path(folder)/"result"
            source = ROOT/"examples/high_support/adaptive_sparse_ghz_20q.sbq"
            result = supervise("generate",source,output,["--budget","1e-4"],128,20)
            self.assertEqual(result["status"],"timeout")
            self.assertEqual(result["stages"][-1]["phase"],"publish")
            self.assertFalse(output.exists())
            self.assertEqual(result["active_after_cleanup"],0)
