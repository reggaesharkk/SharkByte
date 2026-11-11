import argparse
import hashlib
import http.server
import importlib.util
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ORIGINAL = HERE / "sharkbyte_8097.py"

if not ORIGINAL.is_file():
    raise RuntimeError("8097 source file missing")

ORIGINAL_HASH = hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()

spec = importlib.util.spec_from_file_location(
    "sharkbyte_8097_preserved", ORIGINAL
)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load preserved 8097")

engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

engine.RUNS = HERE / "runs"

def skip(s, pos):
    while pos < len(s) and s[pos].isspace():
        pos += 1
    return pos

def block(s, pos, opening="{", closing="}"):
    pos = skip(s, pos)
    if pos >= len(s) or s[pos] != opening:
        raise ValueError("Expected " + opening)
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == opening:
            depth += 1
        elif s[i] == closing:
            depth -= 1
            if depth == 0:
                return s[pos + 1:i], i + 1
    raise ValueError("Unclosed " + opening)

def named(s, pos, word):
    pos = skip(s, pos)
    m = re.match(re.escape(word) + r"\b", s[pos:])
    if not m:
        raise ValueError("Expected " + word + " block")
    return block(s, pos + m.end())

def parse_hybrid(source):
    clean = re.sub(r"//[^\n]*", "", source)
    m = re.match(
        r"\s*hybrid\s+([A-Za-z_][A-Za-z_0-9]*)\s*",
        clean
    )
    if not m:
        raise ValueError("Expected hybrid program declaration")

    body, end = block(clean, m.end())
    if clean[end:].strip():
        raise ValueError("Unexpected text after hybrid program")

    prepare, pos = named(body, 0, "prepare")
    quantum, pos = named(body, pos, "quantum")
    feedback, pos = named(body, pos, "feedback")

    if body[pos:].strip():
        raise ValueError("Unexpected hybrid block")

    return m.group(1), prepare, quantum, feedback

def feedback_ast(source, depth=0):
    if depth > 2:
        raise ValueError("Feedback nesting limit exceeded")
    items = []
    pos = 0

    while skip(source, pos) < len(source):
        pos = skip(source, pos)

        m = re.match(r"print\b", source[pos:])
        if m:
            start = pos + m.end()
            end = source.find(";", start)
            if end < 0:
                raise ValueError("Feedback print requires semicolon")
            expr = source[start:end].strip()
            if not expr:
                raise ValueError("Empty feedback expression")
            items.append(("print", expr))
            pos = end + 1
        else:
            m = re.match(r"if\b", source[pos:])
            if not m:
                raise ValueError(
                    "Feedback supports print and if/else only"
                )

            condition, pos = block(
                source, pos + m.end(), "(", ")"
            )
            positive, pos = block(source, pos)
            negative = ""

            pos = skip(source, pos)
            e = re.match(r"else\b", source[pos:])
            if e:
                negative, pos = block(
                    source, pos + e.end()
                )

            items.append((
                "if", condition,
                feedback_ast(positive, depth + 1),
                feedback_ast(negative, depth + 1)
            ))

        if len(items) > 16:
            raise ValueError("Feedback statement limit exceeded")

    return items

def substitute(expression, variables):
    expression = re.sub(
        r"\$\{([A-Za-z_][A-Za-z_0-9]*)\}",
        lambda match: match.group(1),
        expression
    )

    def replacement(match):
        word = match.group(0)
        if word not in variables:
            raise ValueError("Unknown feedback variable: " + word)
        value = variables[word]
        if type(value) is not int:
            raise ValueError("Feedback variable must be integer")
        return str(value)

    text = re.sub(
        r"\b[A-Za-z_][A-Za-z_0-9]*\b",
        replacement, expression
    ).strip()

    if len(text) > 128 or not re.fullmatch(
        r"[0-9+\-*/()\s]+", text
    ):
        raise ValueError("Unsupported feedback expression")

    if "**" in text or "//" in text:
        raise ValueError("Unsupported arithmetic operation")

    return text

def classical_number(expression, variables, backend):
    text = substitute(expression, variables)
    report = engine.classical(text, backend)
    stdout = report["stdout"].strip()

    if not re.fullmatch(r"-?[0-9]+", stdout):
        raise ValueError("Feedback requires integer result")

    return int(stdout), report["stdout"]

def condition_value(condition, variables, backend):
    m = re.fullmatch(
        r"\s*(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*",
        condition, flags=re.DOTALL
    )
    if not m:
        raise ValueError("Invalid feedback condition")

    left, _ = classical_number(m.group(1), variables, backend)
    right, _ = classical_number(m.group(3), variables, backend)
    operation = m.group(2)

    return {
        "==": lambda: left == right,
        "!=": lambda: left != right,
        ">": lambda: left > right,
        "<": lambda: left < right,
        ">=": lambda: left >= right,
        "<=": lambda: left <= right,
    }[operation]()

def run_feedback(nodes, variables, backend, trace):
    output = []
    for node in nodes:
        if len(trace) >= 40:
            raise ValueError("Feedback execution limit exceeded")

        if node[0] == "print":
            value, stdout = classical_number(
                node[1], variables, backend
            )
            trace.append({
                "type": "print",
                "expression": node[1],
                "value": value
            })
            output.append(stdout)
        else:
            decision = condition_value(
                node[1], variables, backend
            )
            trace.append({
                "type": "if",
                "condition": node[1],
                "condition_result": decision
            })
            branch = node[2] if decision else node[3]
            output.extend(
                run_feedback(branch, variables, backend, trace)
            )
    return output

def enhanced_execute(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")

    if payload.get("mode") != "hybrid":
        return engine.execute(payload)

    source = payload.get("source")
    backend = payload.get("backend", "vm")

    if not isinstance(source, str):
        raise ValueError("Source must be text")
    if len(source.encode("utf-8")) > 65536:
        raise ValueError("Hybrid source too large")
    if backend not in engine.BACKENDS:
        raise ValueError("Unknown classical backend")

    name, prepare, quantum, feedback = parse_hybrid(source)
    instructions = feedback_ast(feedback)

    if not instructions:
        raise ValueError("Empty feedback block")

    # Use the existing 8097 hybrid implementation for
    # preparation, circuit generation, sampling and parity checks.
    canonical = (
        "hybrid " + name + " {\n"
        "prepare {" + prepare + "}\n"
        "quantum {" + quantum + "}\n"
        "feedback { print 0; }\n"
        "}"
    )

    baseline = engine.hybrid_execute(canonical, backend)
    variables = baseline["feedback_variables"]

    if set(variables) != {
        "even_shots", "odd_shots", "total_shots"
    }:
        raise RuntimeError("Unexpected hybrid variable inventory")

    if (
        variables["even_shots"] + variables["odd_shots"]
        != variables["total_shots"]
    ):
        raise RuntimeError("Hybrid shot totals disagree")

    trace = []
    output = run_feedback(
        instructions, variables, backend, trace
    )

    baseline["status"] = "HYBRID_FEEDBACK_EXECUTED"
    baseline["source_sha256"] = hashlib.sha256(
        source.encode("utf-8")
    ).hexdigest()
    baseline["canonical_source_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    baseline["feedback_stdout"] = "".join(output)
    baseline["feedback_trace"] = trace
    baseline["feedback_language"] = (
        "bounded-direct-variables-and-if-else"
    )
    baseline["limitations"] = [
        "Feedback expressions run through the selected classical backend",
        "If/else orchestration is performed by the bounded Python frontend",
        "Quantum mode remains a classical statevector simulation",
        "Only the existing even/odd hybrid circuit patterns are supported",
        "General loops and custom hybrid gate blocks remain unsupported"
    ]

    return 200, baseline

PAGE = engine.PAGE.replace("SharkByte 8097", "SharkByte 8098")
PAGE = PAGE.replace(
    r"print \${even_shots};",
    "print even_shots;"
).replace(
    r"print \${odd_shots};",
    """print odd_shots;
if (even_shots > odd_shots) {
    print total_shots - odd_shots;
} else {
    print 0;
}"""
)

class Handler(engine.Handler):
    def allowed(self):
        return self.headers.get("Host") == "127.0.0.1:8098"

    def do_GET(self):
        if not self.allowed():
            return self.respond(403, {"error": "Invalid host"})

        if self.path == "/":
            return self.send_bytes(
                200, PAGE.encode("utf-8"),
                "text/html; charset=utf-8"
            )

        if self.path == "/health":
            try:
                health = engine.check_engine()
                return self.respond(200, {
                    "status": "ok",
                    "version": "8098-feedback-candidate",
                    "bind": "127.0.0.1:8098",
                    "quantum_backend": health
                })
            except Exception as error:
                return self.respond(
                    503, {"error": str(error)}
                )

        return self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.allowed():
            return self.respond(403, {"error": "Invalid host"})
        if self.path != "/api/run":
            return self.respond(404, {"error": "Not found"})

        origin = self.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:8098":
            return self.respond(403, {"error": "Invalid origin"})

        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, {"error": "Chunked input rejected"})

        if self.headers.get("Content-Type", "").split(";")[0].lower() != "application/json":
            return self.respond(415, {"error": "JSON required"})

        try:
            size = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            size = -1

        if not 0 < size <= 70000:
            return self.respond(413, {"error": "Invalid request size"})

        if not engine.BUSY.acquire(blocking=False):
            return self.respond(503, {"error": "Execution busy"})

        try:
            payload = json.loads(self.rfile.read(size))
            status, report = enhanced_execute(payload)

            if isinstance(payload, dict):
                engine.preserve(payload, status, report)

            return self.respond(status, report)

        except ValueError as error:
            return self.respond(400, {"error": str(error)})
        except Exception as error:
            return self.respond(502, {
                "error": type(error).__name__ + ": " + str(error)
            })
        finally:
            engine.BUSY.release()

def test_source(pattern, shots=256):
    return """hybrid feedback_test {
prepare {
qubits = 6;
shots = """ + str(shots) + """;
seed = 20261109;
}
quantum {
pattern = """ + pattern + """;
}
feedback {
print even_shots;
print odd_shots;
print total_shots - even_shots;
if (odd_shots > even_shots) {
    print 7 + 1;
} else {
    print 0;
}
}
}"""

def selftest():
    sample = test_source("odd")
    _, prep, quantum, feedback = parse_hybrid(sample)

    assert "qubits = 6" in prep
    assert "pattern = odd" in quantum
    assert len(feedback_ast(feedback)) == 4

    assert substitute(
        "odd_shots + ${even_shots}",
        {"odd_shots": 256, "even_shots": 0}
    ) == "256 + 0"

    for bad in ("unknown_variable", "1 ** 1000"):
        try:
            substitute(bad, {})
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid feedback accepted")

    assert "copyOutput.addEventListener" in PAGE
    assert "copyOutput.disabled = !lastText" in PAGE
    assert "SharkByte 8098" in PAGE

    assert hashlib.sha256(
        ORIGINAL.read_bytes()
    ).hexdigest() == ORIGINAL_HASH

    print("8098_FEEDBACK_PARSER=PASS")
    print("8098_VARIABLE_BINDING=PASS")
    print("8098_CONDITIONAL_GRAMMAR=PASS")
    print("8098_COPY_UI_STATIC_CHECK=PASS")
    print("8097_SOURCE_UNCHANGED=PASS")
    print("8098_SELFTEST=PASS")

def integrationtest():
    selftest()
    engine.check_engine()

    for backend in engine.BACKENDS:
        for pattern in ("even", "odd"):
            source = test_source(pattern)
            status, result = enhanced_execute({
                "mode": "hybrid",
                "backend": backend,
                "source": source
            })

            assert status == 200
            assert result["status"] == "HYBRID_FEEDBACK_EXECUTED"

            if pattern == "odd":
                expected = "0\n256\n256\n8\n"
            else:
                expected = "256\n0\n0\n0\n"

            assert result["feedback_stdout"] == expected
            assert result["feedback_variables"]["total_shots"] == 256

            engine.preserve({
                "mode": "hybrid",
                "backend": backend,
                "source": source
            }, status, result)

            print(
                backend.upper() + "_" +
                pattern.upper() + "=PASS",
                flush=True
            )

    assert hashlib.sha256(
        ORIGINAL.read_bytes()
    ).hexdigest() == ORIGINAL_HASH

    print("8098_INTEGRATION=6/6_PASS")
    print("8097_SOURCE_RECHECK=PASS")

def serve():
    engine.check_engine()
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 8098), Handler
    )
    server.daemon_threads = True
    print(
        "SharkByte 8098: http://127.0.0.1:8098/",
        flush=True
    )
    server.serve_forever()

if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument(
        "command",
        choices=("selftest", "integrationtest", "serve")
    )
    args = cli.parse_args()

    if args.command == "selftest":
        selftest()
    elif args.command == "integrationtest":
        integrationtest()
    else:
        serve()