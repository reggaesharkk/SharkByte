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
EXAMPLES = {"classical": "example.sb", "quantum": "bell.sb", "hybrid": "adaptive.sb"}


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
                raise ValueError("Select Classical, Quantum or Hybrid.")
            source = request.get("source")
            if not isinstance(source, str) or len(source.encode()) > MAX_SOURCE_BYTES:
                raise ValueError("Source must be UTF-8 text up to 65,536 bytes.")
        except (ValueError, TypeError) as exc:
            return self.reply(400, {"execution_id": execution_id, "error": str(exc)})

        started = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory(prefix="sharkbyte-studio-") as folder:
                path = Path(folder) / "program.sb"
                path.write_bytes(source.encode())
                completed = subprocess.run(
                    [sys.executable, "-B", "-m", "sharkbyte_alpha", "run", str(path),
                     "--mode", request["mode"], "--backend", "vm"],
                    cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30,
                )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return self.reply(503, {"execution_id": execution_id, "error": str(exc)})

        if completed.returncode:
            return self.reply(422, {"execution_id": execution_id,
                                    "error": completed.stderr.strip() or f"Worker exited with code {completed.returncode}."})
        record = json.loads(completed.stdout)
        bytecode = record.get("bytecode_hex")
        self.reply(200, {"execution_id": execution_id,
                         "worker_wall_seconds": time.perf_counter() - started,
                         "record": record,
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
