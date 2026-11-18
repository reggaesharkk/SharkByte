"""Local-origin, endpoint and receipt regressions for the opt-in Lucid Studio route."""
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sharkbyte_alpha.lucid_dynamics import verify_receipt


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Lucid numerical extra (NumPy + SciPy) is not installed")
class LucidStudioHTTPTests(unittest.TestCase):
    def setUp(self):
        from sharkbyte_studio import Studio
        self.temp = tempfile.TemporaryDirectory()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Studio)
        self.server.receipt_dir = Path(self.temp.name)
        self.server.receipts = {}
        # Existing Studio scaling jobs are not touched by this isolated route.
        self.server.scaling_jobs = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, value=None, origin=None):
        data = json.dumps(value).encode() if value is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if origin:
            headers["Origin"] = origin
        request = Request(self.base + path, data=data, headers=headers)
        try:
            with urlopen(request, timeout=30) as reply:
                return reply.status, reply.read(), reply.headers
        except HTTPError as err:
            return err.code, err.read(), err.headers

    def test_get_page_and_reject_foreign_origin(self):
        status, body, headers = self.request("/lucid")
        self.assertEqual(status, 200)
        self.assertIn(b"Lucid Dynamics", body)
        self.assertIn(b"/lucid/run", body)
        status, _, _ = self.request("/lucid", origin="https://example.com")
        self.assertEqual(status, 403)

    def test_lucid_execution_and_receipt_download(self):
        status, body, _ = self.request("/lucid/run", {"preset": "IVc_pure_psi_memory", "samples": 120})
        self.assertEqual(status, 200, body.decode()[:500])
        data = json.loads(body)
        self.assertTrue(verify_receipt(data["record"]))
        self.assertAlmostEqual(data["record"]["result"]["diagnostics"]["observed_period"], 17.936755, delta=.002)
        status, receipt, headers = self.request(data["receipt_url"])
        self.assertEqual(status, 200)
        self.assertTrue(verify_receipt(json.loads(receipt)))
        self.assertIn("attachment", headers["Content-Disposition"])

    def test_invalid_inputs_and_cross_origin_refused(self):
        status, _, _ = self.request("/lucid/run", {"samples": 999999})
        self.assertEqual(status, 400)
        status, _, _ = self.request("/lucid/run", {"samples": 120}, origin="https://example.com")
        self.assertEqual(status, 403)
        status, _, _ = self.request("/lucid/run", {"parameters": {"lambda_lucid": 9}})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()