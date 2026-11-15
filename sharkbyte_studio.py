"""Launch the local SharkByte Studio with Python 3.10+."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4
import webbrowser

from sharkbyte_alpha import vm
from sharkbyte_alpha.cli import MAX_SOURCE_BYTES


ROOT = Path(__file__).resolve().parent
EXAMPLES = {"classical": "example.sb", "quantum": "bell.sb", "hybrid": "adaptive.sb",
            "frontier": "ghz_phase_30.sb"}


class Studio(BaseHTTPRequestHandler):
    def reply(self, status, value, content_type="application/json"):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        host = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == host and self.headers.get("Origin") in (None, f"http://{host}")

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {"error": "Open Studio from its local launch URL."})
        if self.path == "/":
            return self.reply(200, (ROOT / "sharkbyte_studio.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/examples":
            return self.reply(200, {mode: (ROOT / "examples" / name).read_text(encoding="utf-8")
                                    for mode, name in EXAMPLES.items()})
        self.reply(404, {"error": "Page not found."})

    def do_POST(self):
        execution_id = uuid4().hex
        if not self.local_request():
            return self.reply(403, {"execution_id": execution_id, "error": "Use the local Studio page."})
        if self.path != "/run":
            return self.reply(404, {"execution_id": execution_id, "error": "Endpoint not found."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if self.headers.get_content_type() != "application/json" or not 0 < size <= 6 * MAX_SOURCE_BYTES + 1024:
                raise ValueError("Expected a bounded JSON request.")
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict) or request.get("mode") not in EXAMPLES:
                raise ValueError("Select a supported Studio mode.")
            source = request.get("source")
            if not isinstance(source, str) or len(source.encode()) > MAX_SOURCE_BYTES:
                raise ValueError("Source must be UTF-8 text up to 65,536 bytes.")
            if source.lstrip().startswith("hybrid ") and request["mode"] != "hybrid":
                raise ValueError("Select Bounded Hybrid for a hybrid block. Frontier30 accepts a quantum block with fixed numeric angles.")
            support_cap = request.get("support_cap", 4096)
            if request["mode"] == "frontier" and (type(support_cap) is not int or support_cap not in (4096, 8192, 16384, 32768)):
                raise ValueError("Choose a Frontier30 support cap of 4,096, 8,192, 16,384, or 32,768 states.")
        except (ValueError, TypeError) as exc:
            return self.reply(400, {"execution_id": execution_id, "error": str(exc)})

        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="sharkbyte-studio-") as folder:
                path = Path(folder) / "program.sb"
                path.write_bytes(source.encode())
                if request["mode"] == "frontier":
                    command = ["-c", "import json,sys; from pathlib import Path; "
                               "from sharkbyte_experiment import run_experiment; "
                               "print(json.dumps(run_experiment(Path(sys.argv[1]).read_bytes().decode('utf-8'), 'frontier', int(sys.argv[2]))))",
                               str(path), str(support_cap)]
                else:
                    command = ["-m", "sharkbyte_alpha", "run", str(path),
                               "--mode", request["mode"], "--backend", "vm"]
                completed = subprocess.run(
                    [sys.executable, "-B", *command],
                    cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30,
                )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return self.reply(503, {"execution_id": execution_id, "error": str(exc)})

        if completed.returncode:
            return self.reply(422, {"execution_id": execution_id,
                                    "error": completed.stderr.strip() or f"Worker exited with code {completed.returncode}."})
        record = json.loads(completed.stdout)
        if record["mode"] == "frontier" and record["result"]["result"] != "PASS":
            return self.reply(422, {"execution_id": execution_id, "error": record["result"]["reason"]})
        bytecode = record.get("bytecode_hex")
        self.reply(200, {"execution_id": execution_id,
                         "worker_wall_seconds": time.perf_counter() - started,
                         "record": record,
                         "receipt_json": json.dumps(record, indent=2, allow_nan=False),
                         "disassembly": vm.disassemble(bytes.fromhex(bytecode)) if bytecode else None})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8120)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with HTTPServer(("127.0.0.1", args.port), Studio) as server:
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"SharkByte Studio · {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
