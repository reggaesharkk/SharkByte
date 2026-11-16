"""Exact switching-policy and resource regressions for the experimental simulator."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
for path in (ROOT / "tools" / "high_support", BENCH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from adaptive_statevector import (  # noqa: E402
    AdaptiveStats, evolve_adaptive, to_dense,
)
from dense_statevector import evolve as dense_evolve  # noqa: E402
from sparse_backend import Circuit, ResourceLimitError, evolve as sparse_evolve  # noqa: E402


class AdaptiveStatevectorTests(unittest.TestCase):
    def test_exact_sparse_dense_sparse_roundtrip_matches_both_references(self):
        # The first three Hadamards cross the default density threshold. The
        # inverse gates return the vector to one exact basis state.
        circuit = Circuit(6, tuple(("h", q) for q in (0, 1, 2, 2, 1, 0)),
                          "switch-roundtrip")
        budget = 128 * 512
        stats = AdaptiveStats()
        actual = evolve_adaptive(circuit, support_cap=64, memory_budget_bytes=budget,
                                 stats=stats)
        expected_sparse = sparse_evolve(circuit, support_cap=64,
                                        memory_budget_bytes=64 * 512)
        expected_dense = dense_evolve(circuit.qubits, circuit.gates)
        np.testing.assert_allclose(to_dense(actual, circuit.qubits), expected_dense,
                                   rtol=0.0, atol=2e-15)
        self.assertEqual(set(actual), set(expected_sparse))
        for basis in expected_sparse:
            self.assertAlmostEqual(actual[basis].real, expected_sparse[basis].real, places=15)
            self.assertAlmostEqual(actual[basis].imag, expected_sparse[basis].imag, places=15)
        self.assertEqual(stats.representation, "sparse-dict")
        self.assertEqual([x["from"] + "->" + x["to"] for x in stats.transitions],
                         ["sparse-dict->dense-complex128", "dense-complex128->sparse-dict"])
        self.assertEqual(len(actual), 1)

    def test_tiny_nonzero_amplitudes_are_not_silently_pruned(self):
        angle = 1e-12
        gates = (("ry", 0, angle),) + tuple(("h", q) for q in range(1, 10)) + tuple(
            ("h", q) for q in reversed(range(1, 10)))
        circuit = Circuit(10, gates, "tiny-amplitude-preservation")
        dense = dense_evolve(circuit.qubits, circuit.gates)
        stats = AdaptiveStats()
        actual = evolve_adaptive(circuit, support_cap=1024, memory_budget_bytes=1024 * 512,
                                 dense_enter_density=0.3, dense_leave_density=0.1,
                                 stats=stats)
        converted = to_dense(actual, circuit.qubits)
        np.testing.assert_array_equal(converted, dense)
        self.assertIsInstance(actual, dict)
        self.assertEqual(len(actual), int(np.count_nonzero(dense)))
        self.assertLess(min(abs(value) for value in actual.values()), 1e-11)
        # The tiny exact-nonzero amplitude remains after densification and
        # sparse conversion; the transition uses no magnitude threshold.
        self.assertIn("dense-complex128->sparse-dict",
                      [x["from"] + "->" + x["to"] for x in stats.transitions])

    def test_refuses_transition_before_dense_allocation_if_peak_exceeds_budget(self):
        circuit = Circuit(5, tuple(("h", q) for q in range(5)), "unsafe-transition")
        # At the first dense transition, a 4-entry dict and the 32-element
        # complex array must coexist. 1,000 bytes fits neither transition.
        with mock.patch("adaptive_statevector.np.zeros",
                        side_effect=AssertionError("dense allocation happened before refusal")):
            with self.assertRaises(ResourceLimitError):
                evolve_adaptive(circuit, support_cap=32, memory_budget_bytes=1000,
                                dense_enter_density=0.2)

    def test_progress_and_stats_are_monotone_and_report_representation(self):
        circuit = Circuit(5, tuple(("h", q) for q in range(5)), "progress")
        progress = []
        stats = AdaptiveStats()
        evolve_adaptive(circuit, support_cap=32, memory_budget_bytes=32 * 512,
                        stats=stats,
                        progress_callback=lambda done, total, support, representation:
                        progress.append((done, total, support, representation)))
        self.assertEqual([item[0] for item in progress], list(range(1, 6)))
        self.assertEqual(progress[-1][1], 5)
        self.assertEqual(progress[-1][2], 32)
        self.assertEqual(progress[-1][3], "dense-complex128")
        self.assertEqual(stats.peak_support, 32)

    def test_invalid_policy_and_timeout_are_rejected(self):
        circuit = Circuit(1, (("h", 0),))
        with self.assertRaisesRegex(ValueError, "density thresholds"):
            evolve_adaptive(circuit, support_cap=2, memory_budget_bytes=1024,
                            dense_enter_density=0.1, dense_leave_density=0.1)
        with self.assertRaisesRegex(ValueError, "max_seconds"):
            evolve_adaptive(circuit, support_cap=2, memory_budget_bytes=1024,
                            max_seconds=float("nan"))


if __name__ == "__main__":
    unittest.main()
