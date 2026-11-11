import argparse
import contextvars
import gate2_parent
import hashlib
import http.server
import importlib.util
import json
import math
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PORT = int(os.environ.get("SHARKBYTE_8099B_PORT", "8101"))
PINS = json.loads(
    (HERE / "frozen_pins_8099b.json").read_text(encoding="utf-8-sig")
)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def check_pins():
    for name, expected in PINS.items():
        if sha((HERE / name).read_bytes()).lower() != expected.lower():
            raise RuntimeError("Frozen dependency modified: " + name)

check_pins()

spec = importlib.util.spec_from_file_location(
    "sharkbyte_8099a_frozen_for_8099b",
    HERE / "sharkbyte_8099a.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot import 8099A")

core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

legacy = core.rc
runtime = legacy.engine
runtime.RUNS = HERE / "runs"
runtime.UPSTREAM = os.environ.get("SHARKBYTE_8099B_UPSTREAM", "http://127.0.0.1:8116")
_gate2_state = contextvars.ContextVar("gate2_state", default=None)
_gate2_original_upstream = runtime.upstream
def _gate2_upstream(path, payload=None):
    state = _gate2_state.get()
    native_call = bool(state is not None and isinstance(payload, dict) and payload.get("mode") == "classical" and payload.get("backend") in ("native_interpreter", "direct_native"))
    if native_call:
        state["attempted"] += 1
        payload = {**payload, "gate2_context": state["context"]}
    try:
        status, result = _gate2_original_upstream(path, payload)
    except Exception as exc:
        if native_call: state["errors"].append({"error": type(exc).__name__ + ": " + str(exc), "stage": "upstream"})
        raise
    if native_call:
        ref = result.get("native_evidence") if isinstance(result, dict) else None
        err = result.get("native_evidence_error") if isinstance(result, dict) else None
        if isinstance(ref, dict): state["references"].append(ref)
        if err: state["errors"].append(err)
        if ref is None and err is None: state["errors"].append({"error": "native evidence not returned", "http_status": status})
    return status, result
runtime.upstream = _gate2_upstream

def _gate2_preserve(payload, status, report, state):
    if state is not None and state["attempted"]:
        report = {**report, "native_evidence": {**state["context"], "attempted": state["attempted"], "references": list(state["references"]), "errors": list(state["errors"])}}
    run_id = runtime.preserve(payload, status, report)
    if state is not None and state["attempted"]:
        gate2_parent.add_links(runtime.RUNS, run_id, state)
    return report
def check_isolated_engine():
    status, health = runtime.upstream("/health")
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError("Isolated 8116 health request failed")
    if health.get("bind") != "127.0.0.1:" + runtime.UPSTREAM.rsplit(":", 1)[-1]:
        raise RuntimeError("Unexpected isolated upstream bind")
    if health.get("version") != "8096-ui-cp-experimental-bridge":
        raise RuntimeError("Unexpected isolated 8096 engine version")
    return health
runtime.check_engine = check_isolated_engine

SAMPLE = """hybrid adaptive_phase {
prepare {
qubits = 2;
shots = 2048;
seed = 20261110;
theta = 2.0943951023931953;
step = 0.5235987755982988;
iterations = 4;
}
quantum {
h 0;
h 1;
cp theta 0 1;
h 0;
h 1;
measure_all;
}
feedback {
print count_00;
if (count_00 > count_11) {
print 1;
} else {
print 0;
}
}
update {
if (count_00 < 1750) {
theta = theta - step;
} else {
theta = theta;
}
}
}"""

def parse_adaptive(source):
    clean = re.sub(r"//[^\n]*", "", source)
    m = re.match(
        r"\s*hybrid\s+([A-Za-z_][A-Za-z_0-9]*)\s*",
        clean
    )
    if not m:
        raise ValueError("Expected hybrid program declaration")

    body, end = legacy.block(clean, m.end())
    if clean[end:].strip():
        raise ValueError("Trailing source after program")

    prep, pos = legacy.named(body, 0, "prepare")
    quantum, pos = legacy.named(body, pos, "quantum")
    feedback, pos = legacy.named(body, pos, "feedback")
    update, pos = legacy.named(body, pos, "update")

    if body[pos:].strip():
        raise ValueError("Unexpected extra hybrid blocks")

    return m.group(1), prep, quantum, feedback, update

def settings_from_prepare(prep, backend):
    fields = {}
    for item in prep.split(";"):
        item = item.strip()
        if not item:
            continue

        m = re.fullmatch(
            r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.+)",
            item, re.DOTALL
        )
        if not m:
            raise ValueError("Invalid prepare assignment")

        key, value = m.groups()
        if key in fields:
            raise ValueError("Duplicate prepare field")
        fields[key] = value.strip()

    required = {
        "qubits", "shots", "seed",
        "theta", "step", "iterations"
    }
    if set(fields) != required:
        raise ValueError("Adaptive prepare requires six exact fields")

    original = ";".join(
        key + " = " + fields[key]
        for key in ("qubits", "shots", "seed", "theta")
    ) + ";"

    settings = core.parse_prepare(original, backend)

    count, _ = runtime.integer_expression(
        fields["iterations"], backend
    )
    if not 1 <= count <= 8:
        raise ValueError("Iterations must be 1-8")

    if not core.ANGLE.fullmatch(fields["step"]):
        raise ValueError("step must be a decimal literal")

    step = float(fields["step"])
    if not math.isfinite(step) or not 0 < step <= math.pi:
        raise ValueError("step must be in (0, pi]")

    if settings["seed"] + count - 1 > 2147483647:
        raise ValueError("Seed progression exceeds limit")

    settings["iterations"] = count
    settings["step"] = step
    return settings

def parse_update(update):
    m = re.fullmatch(
        r"\s*if\s*\((.*?)\)\s*"
        r"\{\s*theta\s*=\s*theta\s*([+-])\s*step\s*;\s*\}"
        r"\s*else\s*\{\s*theta\s*=\s*theta\s*;\s*\}\s*",
        update,
        re.DOTALL
    )
    if not m:
        raise ValueError(
            "Update must use bounded if(condition) "
            "{ theta = theta +/- step; } else { theta = theta; }"
        )

    condition, sign = m.groups()
    condition = condition.strip()

    if len(condition) > 128 or not re.fullmatch(
        r"[A-Za-z_0-9+\-*/()<>!=\s]+", condition
    ):
        raise ValueError("Invalid update condition")

    return condition, sign

def decimal(value):
    if not math.isfinite(value) or abs(value) > math.pi:
        raise ValueError("Updated theta outside [-pi, pi]")
    if abs(value) < 1e-14:
        value = 0.0
    return format(value, ".16f").rstrip("0").rstrip(".") or "0"

def single_source(name, settings, quantum, feedback, i, theta):
    return (
        "hybrid " + name + "_iteration_" + str(i) + " {\n"
        + "prepare {\n"
        + "qubits = " + str(settings["qubits"]) + ";\n"
        + "shots = " + str(settings["shots"]) + ";\n"
        + "seed = " + str(settings["seed"] + i) + ";\n"
        + "theta = " + decimal(theta) + ";\n"
        + "}\nquantum {\n" + quantum
        + "\n}\nfeedback {\n" + feedback
        + "\n}\n}\n"
    )

def execute(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    source = payload.get("source")
    backend = payload.get("backend", "vm")

    if not isinstance(source, str):
        raise ValueError("Source must be text")
    if len(source.encode("utf-8")) > 65536:
        raise ValueError("Source exceeds limit")
    if backend not in runtime.BACKENDS:
        raise ValueError("Invalid backend")

    if payload.get("mode") != "hybrid":
        return core.custom_execute(payload)

    # Legacy hybrid programs still use the frozen 8099A route.
    if not re.search(r"\bupdate\s*\{", source):
        return core.custom_execute(payload)

    name, prep, quantum, feedback, update = parse_adaptive(source)
    settings = settings_from_prepare(prep, backend)
    condition, sign = parse_update(update)

    if not legacy.feedback_ast(feedback):
        raise ValueError("Feedback block cannot be empty")

    # Prevalidate the quantum circuit before entering the loop.
    core.build_quantum(quantum, settings)

    theta = settings["theta"]
    step = settings["step"]
    history = []
    best = None
    outputs = []

    for i in range(settings["iterations"]):
        generated = single_source(
            name, settings, quantum, feedback, i, theta
        )

        status, report = core.custom_execute({
            "mode": "hybrid",
            "backend": backend,
            "source": generated
        })

        if status != 200 or report.get("status") != "HYBRID_CUSTOM_QUANTUM_EXECUTED":
            raise RuntimeError("Iteration quantum stage failed")

        variables = report["feedback_variables"]
        q = report["quantum_result"]["result"]
        counts = q["counts"]

        if sum(counts.values()) != settings["shots"]:
            raise RuntimeError("Iteration shot mismatch")

        if abs(q["normalization"] - 1.0) > 1e-10:
            raise RuntimeError("Iteration normalization failure")

        decision = legacy.condition_value(
            condition, variables, backend
        )

        zero_state = "0" * settings["qubits"]
        score = counts[zero_state]

        entry = {
            "iteration": i,
            "theta": theta,
            "zero_state_count": score,
            "zero_state_probability": q["probabilities"][zero_state],
            "update_condition": condition,
            "condition_result": decision,
            "quantum_source_sha256": report["quantum_result"]["source_sha256"],
            "feedback_stdout": report["feedback_stdout"],
            "report": report
        }

        outputs.append(report["feedback_stdout"])

        if best is None or score > best["zero_state_count"]:
            best = {
                "iteration": i,
                "theta": theta,
                "zero_state_count": score,
            }

        if i + 1 < settings["iterations"]:
            if decision:
                candidate = (
                    theta + step if sign == "+" else theta - step
                )
                theta = float(decimal(candidate))

        entry["theta_after_update"] = theta
        history.append(entry)

    return 200, {
        "status": "HYBRID_ITERATIVE_EXECUTED",
        "name": name,
        "source_sha256": sha(source.encode("utf-8")),
        "classical_backend": backend,
        "settings": settings,
        "iterations_executed": len(history),
        "history": history,
        "best_observed": best,
        "feedback_stdout": "".join(outputs),
        "real_quantum_hardware_used": False,
        "limitations": [
            "Classical statevector simulation, not quantum hardware",
            "1-8 iterations; bounded 2-6-qubit quantum circuits",
            "Classical conditions use the selected SharkByte backend",
            "Floating-point theta updates use Python orchestration",
            "Only theta +/- step with a guarded condition is supported",
            "Observed best sample does not prove global optimization"
        ]
    }

PAGE = core.PAGE.replace(
    "SharkByte 8099A", "SharkByte 8099B Audit Development"
).replace(
    "sharkbyte_8099a_", "sharkbyte_8099b_"
)
PAGE = PAGE.replace("sharkbyte_8097_", "sharkbyte_8099b_")

ANCHOR = '<button id="copySource" class="secondary">Copy Source</button>'
if PAGE.count(ANCHOR) != 1 or PAGE.count("</script>") != 1:
    raise RuntimeError("Unexpected frozen UI structure")

PAGE = PAGE.replace(
    ANCHOR,
    ANCHOR + '\n<button id="loadAdaptive" class="secondary">'
    'Load Adaptive Example</button>'
)

LOADER = """
document.getElementById('loadAdaptive').addEventListener('click', () => {
    mode.value = 'hybrid';
    backend.disabled = false;
    source.value = __EXAMPLE__;
    setOutput('');
});
"""

PAGE = PAGE.replace(
    "</script>",
    LOADER.replace("__EXAMPLE__", json.dumps(SAMPLE)) + "\n</script>"
)

class Handler(core.Handler):
    def allowed(self):
        return self.headers.get("Host") == "127.0.0.1:" + str(PORT)

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
                check_pins()
                runtime.check_engine()
                return self.respond(200, {
                    "status": "ok",
                    "version": "8099b-iterative-candidate",
                    "bind": "127.0.0.1:" + str(PORT)
                })
            except Exception as error:
                return self.respond(503, {"error": str(error)})
        return self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error": "Invalid Host"})
        if self.path != "/api/run":
            return self.respond(404, {"error": "Not found"})

        origin = self.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:" + str(PORT):
            return self.respond(403, {"error": "Invalid Origin"})

        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Chunked input rejected"})

        content_type = self.headers.get(
            "Content-Type", ""
        ).split(";")[0].strip().lower()

        if content_type != "application/json":
            return self.respond(415, {"error": "JSON required"})

        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1

        if not 0 < size <= 70000:
            return self.respond(413, {"error": "Invalid request size"})

        if not runtime.BUSY.acquire(blocking=False):
            return self.respond(503, {"error": "Execution busy"})

        state = None
        parent_saved = False
        token = None
        payload = None
        try:
            check_pins()
            payload = json.loads(self.rfile.read(size))
            state = gate2_parent.new_state(payload.get("source")) if isinstance(payload, dict) else None
            if state is not None: token = _gate2_state.set(state)
            status, report = execute(payload)
            report = _gate2_preserve(payload, status, report, state)
            parent_saved = True
            return self.respond(status, report)
        except ValueError as error:
            report = {"error": str(error)}
            if state is not None and state["attempted"] and not parent_saved:
                try: report = _gate2_preserve(payload, 400, report, state)
                except Exception as save_error: report["evidence_persistence_error"] = str(save_error)
            return self.respond(400, report)
        except Exception as error:
            report = {"error": type(error).__name__ + ": " + str(error)}
            if state is not None and state["attempted"] and not parent_saved:
                try: report = _gate2_preserve(payload, 502, report, state)
                except Exception as save_error: report["evidence_persistence_error"] = str(save_error)
            return self.respond(502, report)
        finally:
            if token is not None: _gate2_state.reset(token)
            runtime.BUSY.release()

def selftest():
    name, prep, quantum, feedback, update = parse_adaptive(SAMPLE)
    assert name == "adaptive_phase"
    assert "theta" in prep
    assert "cp theta 0 1" in quantum
    assert legacy.feedback_ast(feedback)

    condition, sign = parse_update(update)
    assert condition == "count_00 < 1750"
    assert sign == "-"

    assert "loadAdaptive" in PAGE
    assert "copyOutput.addEventListener" in PAGE
    assert "sharkbyte_8099b_" in PAGE
    assert "sharkbyte_8097_" not in PAGE

    check_pins()
    print("8099B_ADAPTIVE_GRAMMAR=PASS")
    print("8099B_BOUNDARY_PARSER=PASS")
    print("8099B_COPY_UI_STATIC_CHECK=PASS")
    print("8099B_FROZEN_SOURCE_PINS=PASS")
    print("8099B_SELFTEST=PASS")

def integrationtest():
    selftest()
    runtime.check_engine()

    baseline = None
    for backend in runtime.BACKENDS:
        status, result = execute({
            "mode": "hybrid",
            "backend": backend,
            "source": SAMPLE
        })

        assert status == 200
        assert result["status"] == "HYBRID_ITERATIVE_EXECUTED"
        assert result["iterations_executed"] == 4

        history = result["history"]
        for entry in history:
            theta = entry["theta"]
            actual = entry["zero_state_probability"]
            predicted = (5 + 3 * math.cos(theta)) / 8

            assert abs(actual - predicted) < 1e-10
            assert entry["report"]["quantum_result"]["result"]["shots"] == 2048
            assert entry["report"]["feedback_stdout"].endswith("1\n")

        if baseline is None:
            baseline = result
        else:
            assert [
                x["theta"] for x in history
            ] == [
                x["theta"] for x in baseline["history"]
            ]
            assert [
                x["report"]["quantum_result"]["result"]["counts"]
                for x in history
            ] == [
                x["report"]["quantum_result"]["result"]["counts"]
                for x in baseline["history"]
            ]

        runtime.preserve({
            "mode": "hybrid",
            "backend": backend,
            "source": SAMPLE
        }, status, result)

        print("8099B_" + backend.upper() + "_ADAPTIVE=PASS",flush=True)

    status, old = execute({
        "mode": "hybrid",
        "backend": "vm",
        "source": core.SAMPLE
    })
    assert status == 200
    assert old["status"] == "HYBRID_CUSTOM_QUANTUM_EXECUTED"
    print("8099A_LEGACY_COMPATIBILITY=PASS")

    invalid = (
        SAMPLE.replace("iterations = 4;", "iterations = 9;"),
        SAMPLE.replace("step = 0.5235987755982988;", "step = 4.0;"),
        SAMPLE.replace("theta = 2.0943951023931953;", "theta = 9.0;"),
        SAMPLE.replace("measure_all;", "h 0;"),
    )

    for source in invalid:
        try:
            execute({
                "mode": "hybrid",
                "backend": "vm",
                "source": source
            })
        except ValueError:
            continue
        raise AssertionError("Invalid adaptive program accepted")

    print("8099B_INVALID_PROGRAMS=4/4_PASS")
    check_pins()
    print("8099B_THREE_BACKEND_INTEGRATION=3/3_PASS")
    print("8099B_DEPENDENCIES_UNCHANGED=PASS")

def serve():
    check_pins()
    runtime.check_engine()
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", PORT), Handler
    )
    server.daemon_threads = True
    print("SharkByte 8099B Audit Development: http://127.0.0.1:" + str(PORT) + "/",flush=True)
    server.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("selftest","integrationtest","serve")
    )
    args = parser.parse_args()

    if args.command == "selftest":
        selftest()
    elif args.command == "integrationtest":
        integrationtest()
    else:
        serve()