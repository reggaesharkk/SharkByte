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
