import unittest
from copy import deepcopy
from benchmarks.sb_quantum_benchmark.bounded_support import simulate
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit
from benchmarks.sb_quantum_benchmark.verify_bounded import replay


class BudgetTests(unittest.TestCase):
    def run_case(self, gates, budget="0.0001", protected=()):
        circuit = Circuit(4, tuple(gates))
        state, cert = simulate(circuit, budget, protected=protected, support_cap=16,
                               memory_budget_bytes=8192)
        self.assertEqual(state, replay(circuit, cert))
        return circuit, state, cert

    def test_coherent_accumulation(self):
        circuit, state, cert = self.run_case([("ry", 0, 0.00006)] * 12)
        self.assertEqual(len(cert["events"]), 3)
        self.assertIn(1, state)
        bad = deepcopy(cert)
        bad["events"][0]["ticks"] = 1
        with self.assertRaises(ValueError):
            replay(circuit, bad)

    def test_subnormal_and_protection(self):
        for budget, protected in [("1e-320", ()), ("0.01", (1,))]:
            _, state, cert = self.run_case([("ry", 0, 1e-310)], budget, protected)
            self.assertIn(1, state)
            self.assertFalse(cert["events"])

    def test_flat_state(self):
        _, state, cert = self.run_case([("h", q) for q in range(4)])
        self.assertEqual(len(state), 16)
        self.assertFalse(cert["events"])
from fractions import Fraction
import json
from pathlib import Path


from benchmarks.sb_quantum_benchmark.bounded_support import compact
from benchmarks.sb_quantum_benchmark.sparse_backend import ResourceLimitError


class AuditTests(unittest.TestCase):
    run_case = BudgetTests.run_case

    def test_ledger_metadata_and_witnesses(self):
        circuit, _, cert = self.run_case([("ry", 0, 0.00006)] * 12)
        mutations = [
            lambda c: c.update(interval=2),
            lambda c: c["events"].reverse(),
            lambda c: c["events"][0]["removed"].extend(c["events"][0]["removed"][:1]),
            lambda c: c["events"][0]["removed"][0].__setitem__(1, "invalid"),
            lambda c: c["events"][0].update(ticks=c["events"][0]["ticks"]+1),
            lambda c: c.update(charged_l2="0"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                bad = deepcopy(cert)
                mutate(bad)
                with self.assertRaises(ValueError):
                    replay(circuit, bad)

    def test_exact_charge_boundary(self):
        import math
        tick = Fraction(1, 8)
        for value, expected in [(0.125, 1), (math.nextafter(.125, 1), 2),
                                (math.nextafter(.125, 0), 1), (5e-324, 1)]:
            state = {0: 1+0j, 1: complex(value)}
            charge, _ = compact(state, tick, 2, ())
            self.assertEqual(charge, expected)

    def test_coordinate_moves(self):
        _, state, cert = self.run_case([("ry", 0, 1e-6), ("x", 1)], protected=(1,))
        self.assertEqual(list(state), [2])
        self.assertEqual(cert["events"][0]["removed"][0][0], 3)

    def test_compaction_workspace_and_deadline(self):
        with self.assertRaises(ResourceLimitError):
            compact({0:1+0j,1:0.125+0j}, Fraction(1,4), 1, (), scratch_bytes=100)
        with self.assertRaises(ResourceLimitError):
            compact({0:1+0j}, Fraction(1,4), 1, (), deadline=0)

    def test_archived_cross_environment(self):
        path = Path(__file__).resolve().parents[1] / "evidence/bounded-support-controls.json"
        for case in json.loads(path.read_text())["cases"]:
            circuit = Circuit(8, tuple(tuple(g) for g in case["gates"]))
            self.assertEqual(len(replay(circuit, case["certificate"])), case["final_support"])

    def test_source_binding(self):
        import subprocess
        import sys
        import tempfile
        root = Path(__file__).resolve().parents[1]
        source = root / "examples/high_support/roundtrip_17q.sbq"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps({"source_sha256":"0"*64}))
            result = subprocess.run([sys.executable,"-m","benchmarks.sb_quantum_benchmark.verify_bounded",
                                     str(source),str(path)],cwd=root,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("source digest mismatch",result.stderr)
