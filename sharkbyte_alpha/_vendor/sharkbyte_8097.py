import argparse
import datetime
import hashlib
import http.server
import json
import pathlib
import re
import threading
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
RUNS = ROOT / "runs"
HOST = "127.0.0.1"
PORT = 8097
UPSTREAM = "http://127.0.0.1:8096"
BACKENDS = ("vm", "native_interpreter", "direct_native")
BUSY = threading.BoundedSemaphore(1)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

HYBRID_SAMPLE = """hybrid parity_demo {
    prepare {
        qubits = 2 + 2;
        shots = 1024;
        seed = 20261109;
    }
    quantum {
        pattern = even;
    }
    feedback {
        print ${even_shots};
        print ${odd_shots};
    }
}"""

def digest(data):
    return hashlib.sha256(data).hexdigest()

def upstream(path, payload=None):
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        UPSTREAM + path, data=body, headers=headers
    )
    try:
        with OPENER.open(req, timeout=65) as response:
            status = response.status
            raw = response.read(2097153)
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read(2097153)
    if len(raw) > 2097152:
        raise RuntimeError("8096 response exceeded 2 MiB")
    return status, json.loads(raw)

def check_engine():
    status, health = upstream("/health")
    if status != 200:
        raise RuntimeError("8096 health request failed")
    if health.get("status") != "ok":
        raise RuntimeError("8096 unhealthy")
    if health.get("bind") != "127.0.0.1:8096":
        raise RuntimeError("Unexpected upstream bind")
    if health.get("version") != "8096-ui-cp-experimental-bridge":
        raise RuntimeError("Unexpected 8096 engine version")
    return health

def classical(expression, backend):
    if backend not in BACKENDS:
        raise ValueError("Unknown classical backend")
    expression = expression.strip()
    if len(expression) > 64 or not re.fullmatch(
        r"[0-9+\-*/()\s]+", expression
    ):
        raise ValueError("Unsupported classical expression")
    status, report = upstream("/api/run", {
        "mode": "classical",
        "backend": backend,
        "source": "print " + expression + ";"
    })
    if status != 200 or report.get("status") != "CLASSICAL_EXECUTED":
        raise RuntimeError("Classical execution rejected: " + str(report))
    return report

def integer_expression(expression, backend):
    report = classical(expression, backend)
    stdout = report.get("stdout", "")
    if not re.fullmatch(r"\s*-?[0-9]+\s*", stdout):
        raise ValueError("Classical result must be an integer")
    return int(stdout.strip()), report

def parse_hybrid(source):
    clean = re.sub(r"//[^\n]*", "", source)
    matched = re.fullmatch(
        r"\s*hybrid\s+([A-Za-z_][A-Za-z_0-9]*)\s*"
        r"\{\s*prepare\s*\{(.*?)\}\s*"
        r"quantum\s*\{(.*?)\}\s*"
        r"feedback\s*\{(.*)\}\s*\}\s*",
        clean, re.DOTALL
    )
    if not matched:
        raise ValueError(
            "Hybrid requires prepare, quantum and feedback blocks"
        )
    name, prepare_text, quantum_text, feedback_text = matched.groups()

    prepare = {}
    items = [x.strip() for x in prepare_text.split(";") if x.strip()]
    if len(items) != 3:
        raise ValueError("Prepare requires qubits, shots and seed")
    for item in items:
        pair = re.fullmatch(
            r"(qubits|shots|seed)\s*=\s*(.+)", item, re.DOTALL
        )
        if not pair:
            raise ValueError("Invalid prepare assignment")
        key, value = pair.groups()
        if key in prepare:
            raise ValueError("Duplicate prepare assignment")
        prepare[key] = value.strip()
    if set(prepare) != {"qubits", "shots", "seed"}:
        raise ValueError("Incomplete prepare block")

    qm = re.fullmatch(
        r"\s*pattern\s*=\s*(even|odd)\s*;\s*",
        quantum_text
    )
    if not qm:
        raise ValueError("Quantum supports pattern = even or odd")
    feedback = [
        x.strip() for x in feedback_text.split(";") if x.strip()
    ]
    if not 1 <= len(feedback) <= 10:
        raise ValueError("Feedback requires 1-10 print statements")
    return name, prepare, qm.group(1), feedback

def parity_source(n, shots, seed, pattern):
    gates = []
    if pattern == "odd":
        gates.append("x " + str(n - 1) + ";")
    for i in range(n - 1):
        gates.append("h " + str(i) + ";")
    for i in range(n - 1):
        gates.append("cx " + str(i) + " " + str(n - 1) + ";")
    return (
        "quantum hybrid_parity {\n"
        + "qubits " + str(n) + ";\n"
        + "\n".join(gates) + "\n"
        + "shots " + str(shots) + ";\n"
        + "seed " + str(seed) + ";\n"
        + "measure_all;\n}"
    )

def hybrid_execute(source, backend):
    name, prepare, pattern, feedback = parse_hybrid(source)
    values = {}
    pre_reports = {}
    for field in ("qubits", "shots", "seed"):
        values[field], report = integer_expression(
            prepare[field], backend
        )
        pre_reports[field] = report["stdout_sha256"]

    n, shots, seed = (
        values["qubits"], values["shots"], values["seed"]
    )
    if not 2 <= n <= 6:
        raise ValueError("Hybrid requires 2-6 qubits")
    if not 1 <= shots <= 4096:
        raise ValueError("Hybrid shots must be 1-4096")
    if not 0 <= seed <= 2147483647:
        raise ValueError("Hybrid seed out of range")

    qsrc = parity_source(n, shots, seed, pattern)
    status, quantum = upstream("/api/run", {
        "mode": "quantum", "source": qsrc
    })
    if status != 200 or quantum.get("status") != "QUANTUM_SIMULATION_VERIFIED":
        raise RuntimeError("Quantum stage failed: " + str(quantum))
    if quantum.get("hardware_used") is not False:
        raise RuntimeError("Unexpected quantum hardware claim")

    result = quantum["result"]
    counts = result["counts"]
    if result["qubits"] != n or sum(counts.values()) != shots:
        raise RuntimeError("Quantum output consistency failed")

    even = sum(
        count for state, count in counts.items()
        if state.count("1") % 2 == 0
    )
    odd = shots - even
    if (pattern == "even" and odd != 0) or (
        pattern == "odd" and even != 0
    ):
        raise RuntimeError("Forbidden parity measurement encountered")

    symbols = {
        "even_shots": even,
        "odd_shots": odd,
        "total_shots": shots,
    }
    outputs = []
    for line in feedback:
        if not line.startswith("print "):
            raise ValueError("Only print feedback is supported")
        expression = line[6:]

        def substitute(match):
            key = match.group(1)
            if key not in symbols:
                raise ValueError("Unknown feedback variable: " + key)
            return str(symbols[key])

        expression = re.sub(
            r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}",
            substitute, expression
        )
        response = classical(expression, backend)
        outputs.append(response["stdout"])

    return {
        "status": "HYBRID_EXECUTED",
        "name": name,
        "source_sha256": digest(source.encode("utf-8")),
        "classical_backend": backend,
        "prepare": values,
        "prepare_stdout_sha256": pre_reports,
        "quantum_pattern": pattern,
        "quantum_source": qsrc,
        "quantum_result": quantum,
        "feedback_variables": symbols,
        "feedback_stdout": "".join(outputs),
        "real_quantum_hardware_used": False,
        "limitations": [
            "Bounded prepare/quantum/feedback hybrid subset",
            "Quantum engine is a classical statevector simulator",
            "General classical loops in hybrid programs are not yet supported"
        ]
    }

def execute(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    source = payload.get("source")
    mode = payload.get("mode")
    backend = payload.get("backend", "vm")
    if not isinstance(source, str):
        raise ValueError("Source must be text")
    if len(source.encode("utf-8")) > 65536:
        raise ValueError("Source exceeds 65536 bytes")
    if mode not in ("classical", "quantum", "hybrid"):
        raise ValueError("Unsupported execution mode")
    check_engine()
    if mode == "hybrid":
        return 200, hybrid_execute(source, backend)
    if mode == "classical" and backend not in BACKENDS:
        raise ValueError("Invalid classical backend")
    status, report = upstream("/api/run", {
        "mode": mode,
        "backend": backend,
        "source": source
    })
    return status, report

def preserve(payload, status, report):
    RUNS.mkdir(parents=True, exist_ok=True)
    identifier = (
        datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y%m%dT%H%M%S%fZ")
        + "_" + uuid.uuid4().hex[:8]
    )
    folder = RUNS / identifier
    folder.mkdir(exist_ok=False)
    mode = payload.get("mode", "unknown")
    ext = {
        "classical": ".sb",
        "quantum": ".sbq",
        "hybrid": ".sbh",
    }.get(mode, ".txt")

    source = payload.get("source", "")
    files = {
        "source" + ext: source.encode("utf-8"),
        "result.json": (
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8"),
    }
    for name, raw in files.items():
        (folder / name).write_bytes(raw)
    manifest = {
        "schema": 1,
        "status_code": status,
        "mode": mode,
        "files_sha256": {
            name: digest(raw) for name, raw in files.items()
        },
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8"
    )
    return identifier

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SharkByte 8097 — Integrated IDE</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0d1823;color:#e6f1f8;font:15px system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:24px}
h1{font-size:26px;margin:0 0 7px}
small{color:#9aafbd}
.panel{background:#162936;padding:19px;margin-top:18px;border:1px solid #34505e;border-radius:10px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
select,button,textarea{font:inherit}
select{background:#0a1720;color:white;padding:10px;border:1px solid #486575;border-radius:5px}
button{background:#24b5a4;color:#062018;border:0;padding:10px 16px;cursor:pointer;border-radius:5px;font-weight:700}
button.secondary{background:#314b5a;color:white}
button:disabled{opacity:.45;cursor:not-allowed}
textarea{width:100%;height:300px;background:#08141c;color:#ecf7fa;padding:15px;resize:vertical;border:1px solid #486575;border-radius:6px;font:14px ui-monospace,monospace}
pre{white-space:pre-wrap;word-break:break-word;background:#08141c;padding:15px;border-radius:5px;overflow:auto;min-height:120px;font:13px ui-monospace,monospace}
.header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
#copyStatus{min-width:130px;color:#9cddd6}
</style>
</head>
<body>
<main>
<h1>SharkByte 8097</h1>
<small>Integrated Classical · Quantum · Bounded Hybrid IDE.
Localhost only. Quantum programs run on a classical statevector simulator.</small>
<section class="panel">
  <div class="controls">
    <label>Mode
      <select id="mode">
        <option value="classical">Classical SharkByte</option>
        <option value="quantum">Quantum SharkByte</option>
        <option value="hybrid">Hybrid SharkByte</option>
      </select>
    </label>
    <label>Classical backend
      <select id="backend">
        <option value="vm">SharkVM</option>
        <option value="native_interpreter">Native AArch64 Interpreter</option>
        <option value="direct_native">Direct AArch64</option>
      </select>
    </label>
    <button id="run">Compile and Run</button>
    <button id="copySource" class="secondary">Copy Source</button>
  </div>
  <textarea id="source" spellcheck="false">print 40 + 2;</textarea>
  <small>Ctrl+Enter to run. Inputs are limited to 65,536 UTF-8 bytes.</small>
</section>
<section class="panel">
  <div class="header">
    <h2>Execution result</h2>
    <div class="controls">
      <button id="copyOutput" disabled>Copy Output</button>
      <button id="saveOutput" class="secondary" disabled>Save Output</button>
      <button id="copyQasm" class="secondary" disabled>Copy OpenQASM</button>
      <small id="copyStatus" role="status" aria-live="polite"></small>
    </div>
  </div>
  <pre id="result">Ready.</pre>
</section>
</main>
<script>
const mode = document.getElementById('mode');
const backend = document.getElementById('backend');
const source = document.getElementById('source');
const result = document.getElementById('result');
const run = document.getElementById('run');
const copyOutput = document.getElementById('copyOutput');
const saveOutput = document.getElementById('saveOutput');
const copyQasm = document.getElementById('copyQasm');
const copySource = document.getElementById('copySource');
const copyStatus = document.getElementById('copyStatus');

const samples = {
  classical: 'print 40 + 2;',
  quantum: `quantum bell {
qubits 2;
h 0;
cx 0 1;
shots 1024;
seed 20261109;
measure_all;
}`,
  hybrid: `hybrid parity_demo {
prepare {
qubits = 2 + 2;
shots = 1024;
seed = 20261109;
}
quantum {
pattern = even;
}
feedback {
print \${even_shots};
print \${odd_shots};
}
}`
};

let lastText = '';
let lastQasm = '';

function setOutput(text, qasm='') {
  lastText = String(text);
  lastQasm = qasm;
  result.textContent = lastText || 'Ready.';
  copyOutput.disabled = !lastText;
  saveOutput.disabled = !lastText;
  copyQasm.disabled = !lastQasm;
  copyStatus.textContent = '';
}

async function copyText(text) {
  if (!text) return false;
  try {
    if (!navigator.clipboard || !window.isSecureContext) {
      throw new Error('Modern clipboard unavailable');
    }
    await navigator.clipboard.writeText(text);
    return true;
  } catch (_) {
    const field = document.createElement('textarea');
    field.value = text;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.left = '-9999px';
    document.body.appendChild(field);
    field.focus();
    field.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } finally {
      field.remove();
    }
    return ok;
  }
}

async function copyAndConfirm(text) {
  if (!text) return;
  try {
    const ok = await copyText(text);
    copyStatus.textContent = ok
      ? 'Copied — copy again anytime'
      : 'Clipboard unavailable';
  } catch (error) {
    copyStatus.textContent = 'Copy failed: ' + error.message;
  }
}

copyOutput.addEventListener('click', () => copyAndConfirm(lastText));
copyQasm.addEventListener('click', () => copyAndConfirm(lastQasm));
copySource.addEventListener('click', () => copyAndConfirm(source.value));

saveOutput.addEventListener('click', () => {
  if (!lastText) return;
  let extension = 'txt';
  try {
    JSON.parse(lastText);
    extension = 'json';
  } catch (_) {}
  const blob = new Blob([lastText], {
    type: 'text/plain;charset=utf-8'
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'sharkbyte_8097_' +
    new Date().toISOString().replace(/[:.]/g,'-') +
    '.' + extension;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  copyStatus.textContent = 'Saved';
});

mode.addEventListener('change', () => {
  source.value = samples[mode.value];
  backend.disabled = mode.value === 'quantum';
  setOutput('');
});

async function execute() {
  run.disabled = true;
  setOutput('');
  result.textContent = 'Executing...';
  try {
    const response = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        mode: mode.value,
        backend: backend.value,
        source: source.value
      })
    });
    const data = await response.json();
    const text = (response.ok ? '' : 'REQUEST FAILED\n') +
      JSON.stringify(data, null, 2);
    setOutput(text, data.openqasm || '');
  } catch (error) {
    setOutput('REQUEST FAILED: ' + error.message);
  } finally {
    run.disabled = false;
  }
}

run.addEventListener('click', execute);
source.addEventListener('keydown', event => {
  if (event.ctrlKey && event.key === 'Enter') {
    event.preventDefault();
    if (!run.disabled) execute();
  }
});
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def send_bytes(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def respond(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, data, "application/json; charset=utf-8")

    def allowed(self):
        return self.headers.get("Host") == "127.0.0.1:8097"

    def do_GET(self):
        if not self.allowed():
            return self.respond(403, {"error": "Invalid Host"})
        if self.path == "/":
            return self.send_bytes(
                200, PAGE.encode("utf-8"),
                "text/html; charset=utf-8"
            )
        if self.path == "/health":
            try:
                engine = check_engine()
                return self.respond(200, {
                    "status": "ok",
                    "version": "8097-hybrid-ui-candidate",
                    "upstream": engine,
                })
            except Exception as error:
                return self.respond(503, {"error": str(error)})
        self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error": "Invalid Host"})
        if self.path != "/api/run":
            return self.respond(404, {"error": "Not found"})
        origin = self.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:8097":
            return self.respond(403, {"error": "Invalid Origin"})
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Chunked request rejected"})
        ctype = self.headers.get("Content-Type", "").split(";")[0].lower()
        if ctype != "application/json":
            return self.respond(415, {"error": "JSON required"})
        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1
        if not 0 < size <= 70000:
            return self.respond(413, {"error": "Invalid size"})
        if not BUSY.acquire(blocking=False):
            return self.respond(503, {"error": "Execution busy"})
        try:
            payload = json.loads(self.rfile.read(size))
            status, report = execute(payload)
            preserve(payload, status, report)
            return self.respond(status, report)
        except ValueError as error:
            return self.respond(400, {"error": str(error)})
        except Exception as error:
            return self.respond(502, {
                "error": type(error).__name__ + ": " + str(error)
            })
        finally:
            BUSY.release()

def selftest():
    name, prepare, pattern, feedback = parse_hybrid(HYBRID_SAMPLE)
    assert name == "parity_demo"
    assert pattern == "even"
    assert len(prepare) == 3
    assert len(feedback) == 2
    q = parity_source(4, 1024, 20261109, "even")
    assert q.count("cx ") == 3
    assert q.count("h ") == 3
    for identifier in (
        'id="copyOutput"', 'id="saveOutput"',
        'id="copySource"', 'id="copyQasm"',
        'value="hybrid"'
    ):
        assert identifier in PAGE
    assert "copyOutput.addEventListener" in PAGE
    print("8097_HYBRID_PARSER=PASS")
    print("8097_QUANTUM_GENERATOR=PASS")
    print("8097_REPEATABLE_COPY_UI_STATIC_CHECK=PASS")
    print("8097_LOCAL_SELFTEST=PASS")

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("command", choices=("selftest", "serve"))
    args = cli.parse_args()
    if args.command == "selftest":
        selftest()
    else:
        check_engine()
        server = http.server.ThreadingHTTPServer(
            (HOST, PORT), Handler
        )
        print(
            "SharkByte 8097: http://127.0.0.1:8097/",
            flush=True
        )
        server.serve_forever()