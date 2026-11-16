"""Safety and receipt regressions for Studio's high-support worker path."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import unittest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
for path in (ROOT, BENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sharkbyte_alpha.cli import verify as verify_integrity
from sparse_backend import Circuit, evolve
from support_scaling import build_circuit
from sharkbyte_studio import Studio, ThreadingHTTPServer
from tools.studio_scaling_jobs import (
    MIN_AVAILABLE_MEMORY_BYTES, STATES, ScalingJobManager, StudioResourceRefusal,
)
from tools.verify_studio_scaling_receipt import verify_studio_scaling_record


class FakeLimiter:
    def __init__(self, process, peak=128 * 1024**2):
        self.process = process
        self.peak = peak
        self.closed = False

    def peak_memory_bytes(self):
        return self.peak

    def terminate(self, code=1):
        if self.process.poll() is None:
            self.process.kill()

    def close(self):
        self.closed = True


def wait_for(manager, execution_id, terminal, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = manager.snapshot(execution_id)
        if value and value["status"] in terminal:
            return value
        time.sleep(0.025)
    raise AssertionError(f"job did not reach a terminal state: {manager.snapshot(execution_id)}")


class StudioScalingJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="studio-scaling-test-")
        self.addCleanup(self.temp.cleanup)
        self.receipt_dir = Path(self.temp.name)
        self.receipts = {}
        self.source = (ROOT / "examples" / "frontier_sparse_40_131072.sb").read_text(encoding="utf-8")

    def manager(self, command_builder, **kwargs):
        return ScalingJobManager(
            self.receipt_dir, self.receipts,
            memory_provider=lambda: MIN_AVAILABLE_MEMORY_BYTES + 1024**3,
            minimum_available_memory_bytes=0,
            process_memory_limit_bytes=512 * 1024**2,
            command_builder=command_builder,
            process_limiter=lambda process, limit: FakeLimiter(process),
            **kwargs,
        )

    def test_progress_observer_does_not_change_sparse_state(self):
        circuit = Circuit(5, (("h", 0), ("h", 2), ("cx", 0, 1),
                              ("cp", 1, 3, 0.4), ("ry", 4, -0.3)))
        expected = evolve(circuit, support_cap=8, memory_budget_bytes=8 * 512)
        progress = []
        actual = evolve(circuit, support_cap=8, memory_budget_bytes=8 * 512,
                        progress_callback=lambda done, total, states:
                        progress.append((done, total, states)))
        self.assertEqual(actual, expected)
        self.assertEqual(progress[-1], (len(circuit.gates), len(circuit.gates), len(actual)))
        self.assertEqual([event[0] for event in progress], list(range(1, len(circuit.gates) + 1)))

    def test_low_memory_refuses_before_worker_launch(self):
        manager = ScalingJobManager(
            self.receipt_dir, self.receipts, memory_provider=lambda: MIN_AVAILABLE_MEMORY_BYTES - 1,
            command_builder=lambda _: self.fail("worker launched despite preflight refusal"),
        )
        with self.assertRaises(StudioResourceRefusal) as caught:
            manager.start(self.source)
        self.assertEqual(caught.exception.available_bytes, MIN_AVAILABLE_MEMORY_BYTES - 1)
        self.assertEqual(caught.exception.required_bytes, MIN_AVAILABLE_MEMORY_BYTES)
        self.assertFalse(manager._jobs)

    def test_timeout_terminates_worker(self):
        manager = self.manager(
            lambda _: [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout_seconds=0.2,
        )
        execution_id = manager.start(self.source)
        result = wait_for(manager, execution_id, {"timed_out"})
        self.assertIn("0.2-second limit", result["error"])
        self.assertIsNone(manager._jobs[execution_id]["process"])

    def test_cancel_terminates_worker_and_cleans_process(self):
        manager = self.manager(lambda _: [sys.executable, "-c", "import time; time.sleep(5)"])
        execution_id = manager.start(self.source)
        self.assertEqual(manager.cancel(execution_id)["status"], "cancelling")
        result = wait_for(manager, execution_id, {"cancelled"})
        self.assertIn("cancelled by user", result["error"])
        self.assertIsNone(manager._jobs[execution_id]["process"])

    def test_nonzero_worker_is_a_failure_not_a_passing_receipt(self):
        manager = self.manager(lambda _: [sys.executable, "-c",
                                          "import sys; print('controlled worker failure', file=sys.stderr); sys.exit(7)"])
        execution_id = manager.start(self.source)
        result = wait_for(manager, execution_id, {"failed"})
        self.assertIn("controlled worker failure", result["error"])
        self.assertNotIn(execution_id, self.receipts)

    def test_compact_success_receipt_verifies_and_has_no_amplitude_table(self):
        circuit, source_hash, added, _ = build_circuit(STATES)
        report = {
            "status": "PASS", "qubits": 40, "gates": len(circuit.gates),
            "source_sha256": source_hash, "added_gates": [list(gate) for gate in added],
            "peak_active_states": STATES, "final_active_states": STATES,
            "estimated_budget_bytes": STATES * 512, "evolution_seconds": 12.5,
            "probability_sum": 1.0, "max_uniform_probability_error": 0.0,
        }
        encoded = json.dumps(report, sort_keys=True)
        command = lambda _: [sys.executable, "-c", f"print({json.dumps(encoded)})"]
        manager = self.manager(command)
        execution_id = manager.start(self.source)
        completed = wait_for(manager, execution_id, {"completed"})
        record = completed["record"]
        self.assertEqual(verify_integrity(record)["status"], "INTEGRITY_VERIFIED")
        verified = verify_studio_scaling_record(record)
        self.assertEqual(verified["status"], "STUDIO_SCALING_RECEIPT_VERIFIED")
        self.assertEqual(record["result"]["circuit_identity"]["gate_count"], 56)
        self.assertEqual(len(record["result"]["circuit_identity"]["gates"]), 56)
        self.assertNotIn("probabilities", record["result"])
        self.assertLess(len(json.dumps(record)), 32_000)


class StudioHttpIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="studio-http-test-")
        self.addCleanup(self.temp.cleanup)
        self.receipts = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Studio)
        self.server.receipt_dir = Path(self.temp.name)
        self.server.receipts = self.receipts
        self.server.scaling_jobs = ScalingJobManager(
            self.server.receipt_dir, self.receipts,
            memory_provider=lambda: MIN_AVAILABLE_MEMORY_BYTES - 1,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close_server)

    def close_server(self):
        if self.server:
            self.server.scaling_jobs.shutdown()
            self.server.shutdown()
            self.thread.join(timeout=3)
            self.server.server_close()
            self.server = None

    def get_json(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, json.loads(response.read())

    def post_json(self, path, value):
        request = urllib.request.Request(
            self.base + path, data=json.dumps(value).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            finally:
                exc.close()
        with response:
            return response.status, json.loads(response.read())

    def test_studio_exposes_16m_and_fails_closed_on_live_memory_refusal(self):
        status, examples = self.get_json("/examples")
        self.assertEqual(status, 200)
        self.assertIn("scaling_16m", examples)
        self.assertEqual(examples["scaling_16m"], self.source())
        status, result = self.post_json("/run", {
            "mode": "scaling_16m", "source": examples["scaling_16m"]})
        self.assertEqual(status, 503)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["available_memory_bytes"], MIN_AVAILABLE_MEMORY_BYTES - 1)
        self.assertEqual(self.server.scaling_jobs._jobs, {})

    def test_existing_classical_run_and_receipt_download_still_work(self):
        source = (ROOT / "examples" / "example.sb").read_text(encoding="utf-8")
        status, result = self.post_json("/run", {"mode": "classical", "source": source})
        self.assertEqual(status, 200, result)
        self.assertEqual(result["record"]["result"]["stdout"], "42\n")
        request = urllib.request.Request(self.base + result["receipt_url"])
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            receipt = json.loads(response.read())
            self.assertEqual(receipt["source"], source)

    def test_large_run_cancel_endpoint_stops_worker(self):
        self.server.scaling_jobs = ScalingJobManager(
            self.server.receipt_dir, self.receipts,
            memory_provider=lambda: MIN_AVAILABLE_MEMORY_BYTES + 1,
            process_memory_limit_bytes=512 * 1024**2,
            minimum_available_memory_bytes=MIN_AVAILABLE_MEMORY_BYTES,
            command_builder=lambda _: [sys.executable, "-c", "import time; time.sleep(30)"],
            process_limiter=lambda process, limit: FakeLimiter(process),
        )
        status, started = self.post_json("/run", {
            "mode": "scaling_16m", "source": self.source()})
        self.assertEqual(status, 202)
        execution_id = started["execution_id"]
        status, cancelled = self.post_json(f"/jobs/{execution_id}/cancel", {})
        self.assertEqual(status, 202)
        self.assertEqual(cancelled["status"], "cancelling")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status, snapshot = self.get_json(f"/jobs/{execution_id}")
            if snapshot["status"] == "cancelled":
                break
            time.sleep(0.025)
        self.assertEqual(snapshot["status"], "cancelled")
        self.assertIsNone(self.server.scaling_jobs._jobs[execution_id]["process"])

    @staticmethod
    def source():
        return (ROOT / "examples" / "frontier_sparse_40_131072.sb").read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
