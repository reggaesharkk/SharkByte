"""Negative, boundary, receipt, and recovery checks for standalone alpha."""
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

from sharkbyte_alpha import cli, hybrid, quantum

def invoke(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = cli.main(args)
    return status, out.getvalue(), err.getvalue()

class ReleaseEdges(unittest.TestCase):
    def test_native_backend_refusal_precedes_launch(self):
        for backend in ("native_interpreter", "direct_native"):
            for mode in ("classical", "quantum", "hybrid"):
                status, _, err = invoke(["run", "examples/example.sb", "--mode", mode, "--backend", backend])
                self.assertEqual(status, 1)
                self.assertIn("native backends are disabled: containment unavailable", err)

    def test_malformed_classical_and_vm_step_limit(self):
        with tempfile.TemporaryDirectory() as td:
            bad = pathlib.Path(td) / "bad.sb"
            bad.write_text("print ;", encoding="utf-8")
            status, _, err = invoke(["run", str(bad)])
            self.assertNotEqual(status, 0)
            self.assertTrue(err.startswith("sharkbyte:"))
            loop = pathlib.Path(td) / "loop.sb"
            loop.write_text("while (1 == 1) { print 1; }", encoding="utf-8")
            with mock.patch.object(cli, "VM_STEPS", 20):
                status, _, err = invoke(["run", str(loop)])
            self.assertEqual(status, 1)
            self.assertTrue(err.startswith("sharkbyte:"))

    def test_source_encoding_and_size_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "source.sb"
            path.write_bytes(b"\xff")
            with self.assertRaises(UnicodeDecodeError): cli.read_source(path)
            path.write_bytes(b" " * (cli.MAX_SOURCE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "65536"): cli.read_source(path)

    def test_quantum_parameter_and_structure_negatives(self):
        cases = ("qubits 0; measure_all;", "qubits 7; measure_all;", "qubits 2; shots 0; measure_all;",
                 "qubits 2; shots 100001; measure_all;", "qubits 2; cp nan 0 1; measure_all;",
                 "qubits 2; cp inf 0 1; measure_all;", "qubits 2; cp 1 0 0; measure_all;",
                 "qubits 2; cx 0 0; measure_all;", "qubits 2; measure_all; h 0;",
                 "qubits 2; h 2; measure_all;", "qubits 2; h 0;")
        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(ValueError): quantum.parse(source)
        with self.assertRaises(ValueError): quantum.parse("qubits 2;" + " h 0;" * 257 + " measure_all;")

    def test_seeded_sampling_and_normalization(self):
        source = pathlib.Path("examples/bell.sb").read_text(encoding="utf-8")
        first = quantum.evaluate(cli.parse_quantum(source)); second = quantum.evaluate(cli.parse_quantum(source))
        self.assertEqual(first["counts"], second["counts"])
        self.assertAlmostEqual(sum(first["probabilities"].values()), 1.0, delta=1e-10)
        self.assertEqual(sum(first["counts"].values()), first["shots"])

    def test_hybrid_bounds_determinism_and_recovery(self):
        source = pathlib.Path("examples/adaptive.sb").read_text(encoding="utf-8")
        result = hybrid.run(source)
        self.assertEqual(result["iterations_executed"], 4)
        self.assertEqual([r["zero_state_count"] for r in result["history"]], [906, 1250, 1675, 1950])
        self.assertEqual(hybrid.run(source)["history"], result["history"])
        with self.assertRaises(ValueError): hybrid.run(source.replace("iterations = 4", "iterations = 9"))
        recovered = json.loads(invoke(["run", "examples/example.sb"])[1])
        self.assertEqual(recovered["result"]["stdout"], "42\n")

    def test_qasm_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            target = pathlib.Path(td) / "bell.qasm"
            status, _, err = invoke(["qasm", "examples/bell.sb", "--output", str(target)])
            self.assertEqual(status, 0, err)
            self.assertIn("OPENQASM 3.0;", target.read_text(encoding="utf-8"))
            status, _, err = invoke(["qasm", "examples/bell.sb", "--output", str(target)])
            self.assertEqual(status, 1)
            self.assertTrue(err.startswith("sharkbyte:"))

    def test_tampered_receipt_and_native_refusal(self):
        status, out, _ = invoke(["run", "examples/example.sb"])
        self.assertEqual(status, 0)
        record = json.loads(out); record["result"]["stdout"] = "41\n"
        with self.assertRaises(ValueError): cli.verify(record)
        for backend in ("native_interpreter", "direct_native"):
            status, _, err = invoke(["run", "examples/example.sb", "--backend", backend])
            self.assertEqual(status, 1); self.assertIn("containment unavailable", err)

if __name__ == "__main__": unittest.main(verbosity=2)
