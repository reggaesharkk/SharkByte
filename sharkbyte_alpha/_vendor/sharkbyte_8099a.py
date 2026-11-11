import argparse
import hashlib
import http.server
import importlib.util
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PINS = json.loads((HERE / "source_pins.json").read_text(
    encoding="utf-8-sig"
))

def sha(data):
    return hashlib.sha256(data).hexdigest()

def check_sources():
    for name, expected in PINS.items():
        if sha((HERE / name).read_bytes()).lower() != expected.lower():
            raise RuntimeError("Frozen dependency mismatch: " + name)

check_sources()

spec = importlib.util.spec_from_file_location(
    "sharkbyte_8098_frozen_for_8099a",
    HERE / "sharkbyte_8098.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot import frozen 8098")
rc = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rc
spec.loader.exec_module(rc)

rc.engine.RUNS = HERE / "runs"

ANGLE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)")

SAMPLE = """hybrid custom_phase {
prepare {
qubits = 2;
shots = 1024;
seed = 20261110;
theta = 1.0471975511965976;
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
print top_state_count;
if (count_00 > count_11) {
print 1;
} else {
print 0;
}
}
}"""

def parse_prepare(text, backend):
    fields = {}
    for statement in text.split(";"):
        statement = statement.strip()
        if not statement:
            continue
        pair = re.fullmatch(
            r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.+)",
            statement, flags=re.DOTALL
        )
        if not pair:
            raise ValueError("Invalid prepare assignment")
        key, value = pair.groups()
        if key in fields:
            raise ValueError("Duplicate prepare field")
        if key not in ("qubits","shots","seed","theta"):
            raise ValueError("Unsupported prepare field: " + key)
        fields[key] = value.strip()

    if not {"qubits","shots","seed"}.issubset(fields):
        raise ValueError("Missing qubits, shots or seed")
    if len(fields) > 4:
        raise ValueError("Too many prepare fields")

    result = {}
    for field in ("qubits","shots","seed"):
        number, _ = rc.engine.integer_expression(
            fields[field], backend
        )
        result[field] = number

    if not 2 <= result["qubits"] <= 6:
        raise ValueError("Custom hybrid supports 2-6 qubits")
    if not 1 <= result["shots"] <= 4096:
        raise ValueError("Shots must be 1-4096")
    if not 0 <= result["seed"] <= 2147483647:
        raise ValueError("Seed out of range")

    if "theta" in fields:
        if not ANGLE.fullmatch(fields["theta"]):
            raise ValueError("theta must be a finite decimal literal")
        theta = float(fields["theta"])
        if not math.isfinite(theta) or abs(theta) > math.pi:
            raise ValueError("theta must be within [-pi, pi]")
        result["theta"] = theta

    return result

def build_quantum(text, settings):
    n = settings["qubits"]
    statements = [
        x.strip() for x in text.split(";") if x.strip()
    ]

    if not statements or statements[-1] != "measure_all":
        raise ValueError("Custom circuit must end in measure_all")

    gates = []
    for line in statements[:-1]:
        parts = line.split()
        if not parts:
            continue

        op = parts[0]
        arity = {"h":1,"x":1,"z":1,"cx":2,"cp":3}.get(op)
        if arity is None or len(parts) != arity + 1:
            raise ValueError("Unsupported quantum gate: " + line)

        operands = parts[1:]
        if op == "cp":
            angle_text = operands[0]
            if angle_text == "theta":
                if "theta" not in settings:
                    raise ValueError("theta was not declared")
                angle = settings["theta"]
            else:
                if not ANGLE.fullmatch(angle_text):
                    raise ValueError("Invalid cp angle")
                angle = float(angle_text)

            if not math.isfinite(angle) or abs(angle) > math.pi:
                raise ValueError("cp angle outside [-pi, pi]")
            operands = operands[1:]
        else:
            angle = None

        if not all(re.fullmatch(r"[0-9]+", x) for x in operands):
            raise ValueError("Invalid qubit index")

        indexes = [int(x) for x in operands]
        if any(x >= n for x in indexes):
            raise ValueError("Qubit index out of range")
        if len(set(indexes)) != len(indexes):
            raise ValueError("Control and target must differ")

        if op == "cp":
            normalized = "cp " + repr(angle)
        else:
            normalized = op

        gates.append(
            normalized + " " + " ".join(map(str,indexes)) + ";"
        )

        if len(gates) > 256:
            raise ValueError("Gate count exceeds 256")

    if not gates:
        raise ValueError("At least one quantum gate required")

    return (
        "quantum hybrid_custom {\n"
        + "qubits " + str(n) + ";\n"
        + "\n".join(gates) + "\n"
        + "shots " + str(settings["shots"]) + ";\n"
        + "seed " + str(settings["seed"]) + ";\n"
        + "measure_all;\n}"
    )

def custom_execute(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    if payload.get("mode") != "hybrid":
        return rc.enhanced_execute(payload)

    source = payload.get("source")
    backend = payload.get("backend", "vm")

    if not isinstance(source, str):
        raise ValueError("Source must be text")
    if len(source.encode("utf-8")) > 65536:
        raise ValueError("Source exceeds limit")
    if backend not in rc.engine.BACKENDS:
        raise ValueError("Invalid backend")

    name, prepare, quantum, feedback = rc.parse_hybrid(source)

    if re.fullmatch(
        r"\s*pattern\s*=\s*(even|odd)\s*;\s*",
        quantum
    ):
        return rc.enhanced_execute(payload)

    nodes = rc.feedback_ast(feedback)
    if not nodes:
        raise ValueError("Empty feedback block")

    settings = parse_prepare(prepare, backend)
    generated = build_quantum(quantum, settings)

    status, q = rc.engine.upstream("/api/run", {
        "mode":"quantum", "source":generated
    })

    if status != 200 or q.get("status") != "QUANTUM_SIMULATION_VERIFIED":
        raise ValueError("Quantum circuit rejected: " + str(q))

    result = q["result"]
    counts = result["counts"]
    probs = result["probabilities"]

    if result["qubits"] != settings["qubits"]:
        raise RuntimeError("Quantum qubit count mismatch")
    if sum(counts.values()) != settings["shots"]:
        raise RuntimeError("Quantum shots mismatch")
    if abs(result["normalization"] - 1.0) > 1e-10:
        raise RuntimeError("Quantum normalization mismatch")
    if result["reference_max_amplitude_error"] > 1e-11:
        raise RuntimeError("Quantum reference mismatch")
    if q["source_sha256"] != sha(generated.encode("utf-8")):
        raise RuntimeError("Quantum source identity mismatch")
    if set(counts) != set(probs):
        raise RuntimeError("Measurement state inventory mismatch")

    even = sum(
        count for bits,count in counts.items()
        if bits.count("1") % 2 == 0
    )
    top = sorted(
        counts, key=lambda bits:(-counts[bits],int(bits,2))
    )[0]

    variables = {
        "even_shots":even,
        "odd_shots":settings["shots"] - even,
        "total_shots":settings["shots"],
        "top_state_index":int(top,2),
        "top_state_count":counts[top],
        "observed_states":sum(v > 0 for v in counts.values())
    }
    for bits, count in counts.items():
        variables["count_" + bits] = count

    trace = []
    output = rc.run_feedback(
        nodes, variables, backend, trace
    )

    return 200, {
        "status":"HYBRID_CUSTOM_QUANTUM_EXECUTED",
        "name":name,
        "source_sha256":sha(source.encode("utf-8")),
        "classical_backend":backend,
        "prepare":settings,
        "quantum_source":generated,
        "quantum_result":q,
        "openqasm":q["openqasm"],
        "feedback_variables":variables,
        "top_state":top,
        "feedback_stdout":"".join(output),
        "feedback_trace":trace,
        "real_quantum_hardware_used":False,
        "limitations":[
            "Quantum computation is classical statevector simulation",
            "Custom hybrid circuits support 2-6 qubits and 256 gates",
            "theta must be a finite bounded decimal literal",
            "Feedback variables are integers; no float updates",
            "No iterative quantum-classical loops yet"
        ]
    }

PAGE = rc.PAGE.replace(
    "SharkByte 8098", "SharkByte 8099A"
).replace(
    "sharkbyte_8097_", "sharkbyte_8099a_"
)

PAGE = PAGE.replace(
    "seed = 20261109;\n}\nquantum {",
    "seed = 20261110;\ntheta = 1.0471975511965976;\n}\nquantum {"
).replace(
    "pattern = even;",
    "h 0;\nh 1;\ncp theta 0 1;\nh 0;\nh 1;\nmeasure_all;"
).replace(
    "print even_shots;",
    "print count_00;"
).replace(
    "print odd_shots;",
    "print top_state_count;"
)

class Handler(rc.Handler):
    def allowed(self):
        return self.headers.get("Host") == "127.0.0.1:8099"

    def do_GET(self):
        if not self.allowed():
            return self.respond(403, {"error":"Invalid Host"})
        if self.path == "/":
            return self.send_bytes(
                200, PAGE.encode("utf-8"),
                "text/html; charset=utf-8"
            )
        if self.path == "/health":
            try:
                rc.engine.check_engine()
                check_sources()
                return self.respond(200, {
                    "status":"ok",
                    "version":"8099a-custom-hybrid-candidate",
                    "bind":"127.0.0.1:8099"
                })
            except Exception as error:
                return self.respond(503, {"error":str(error)})
        return self.respond(404, {"error":"Not found"})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error":"Invalid Host"})
        if self.path != "/api/run":
            return self.respond(404, {"error":"Not found"})
        origin = self.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:8099":
            return self.respond(403, {"error":"Invalid Origin"})
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error":"Chunked input rejected"})
        content_type = self.headers.get(
            "Content-Type",""
        ).split(";")[0].strip().lower()
        if content_type != "application/json":
            return self.respond(415, {"error":"JSON required"})

        try:
            size = int(self.headers.get("Content-Length","-1"))
        except ValueError:
            size = -1
        if not 0 < size <= 70000:
            return self.respond(413, {"error":"Invalid request size"})

        if not rc.engine.BUSY.acquire(blocking=False):
            return self.respond(503, {"error":"Execution busy"})

        try:
            check_sources()
            payload = json.loads(self.rfile.read(size))
            status, report = custom_execute(payload)
            rc.engine.preserve(payload, status, report)
            return self.respond(status, report)
        except ValueError as error:
            return self.respond(400, {"error":str(error)})
        except Exception as error:
            return self.respond(502, {
                "error":type(error).__name__ + ": " + str(error)
            })
        finally:
            rc.engine.BUSY.release()

def selftest():
    name, prepare, quantum, feedback = rc.parse_hybrid(SAMPLE)
    assert name == "custom_phase"
    assert "theta" in prepare
    assert len(rc.feedback_ast(feedback)) == 3
    assert "copyOutput.addEventListener" in PAGE
    assert "sharkbyte_8099a_" in PAGE
    check_sources()
    print("8099A_PARSER=PASS")
    print("8099A_COPY_UI_STATIC_CHECK=PASS")
    print("8098_RC_SOURCE_PINS=PASS")

def integrationtest():
    selftest()
    rc.engine.check_engine()

    for theta,expected in (
        ("0.0",1.0),
        ("1.0471975511965976",0.8125)
    ):
        baseline = None
        for backend in rc.engine.BACKENDS:
            source = SAMPLE.replace(
                "theta = 1.0471975511965976;",
                "theta = " + theta + ";"
            ).replace(
                "shots = 1024;", "shots = 256;"
            )

            status,report = custom_execute({
                "mode":"hybrid",
                "backend":backend,
                "source":source
            })
            assert status == 200
            assert report["status"] == "HYBRID_CUSTOM_QUANTUM_EXECUTED"

            q = report["quantum_result"]["result"]
            p = q["probabilities"]
            assert abs(p["00"] - expected) < 1e-10

            for bits in ("01","10","11"):
                target = (1.0 - expected) / 3.0
                assert abs(p[bits] - target) < 1e-10

            if baseline is None:
                baseline = report
            else:
                assert report["feedback_stdout"] == baseline["feedback_stdout"]
                assert report["quantum_result"]["result"]["counts"] == baseline["quantum_result"]["result"]["counts"]

            rc.engine.preserve({
                "mode":"hybrid",
                "backend":backend,
                "source":source
            },status,report)

            print(
                "8099A_" + backend.upper() +
                "_THETA_" + theta.replace(".","_") +
                "=PASS", flush=True
            )

    old = """hybrid legacy_test {
prepare {
qubits = 2;
shots = 256;
seed = 20261110;
}
quantum {
pattern = odd;
}
feedback {
print odd_shots;
}
}"""
    status,report = custom_execute({
        "mode":"hybrid","backend":"vm","source":old
    })
    assert status == 200
    assert report["feedback_stdout"] == "256\n"
    print("8098_HYBRID_LEGACY_COMPATIBILITY=PASS")

    for bad in (
        SAMPLE.replace("cp theta 0 1;", "cp theta 0 0;"),
        SAMPLE.replace("qubits = 2;", "qubits = 7;"),
        SAMPLE.replace(
            "theta = 1.0471975511965976;",
            "theta = 9.0;"
        ),
        SAMPLE.replace("measure_all;", "h 0;")
    ):
        try:
            custom_execute({
                "mode":"hybrid","backend":"vm","source":bad
            })
        except ValueError:
            continue
        raise AssertionError("Invalid custom hybrid accepted")

    print("8099A_INVALID_PROGRAMS=4/4_PASS")
    check_sources()
    print("8099A_INTEGRATION=6/6_PASS")
    print("8098_RC_SOURCES_UNCHANGED=PASS")

def serve():
    rc.engine.check_engine()
    check_sources()
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1",8099),Handler
    )
    server.daemon_threads = True
    print(
        "SharkByte 8099A: http://127.0.0.1:8099/",
        flush=True
    )
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