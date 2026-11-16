"""Structure and metamorphic tests for the fixed connected-circuit corpus."""
import hashlib
import cmath
import math
import sys
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "benchmarks" / "sb_quantum_benchmark"
for item in (str(ROOT), str(BENCHMARK_DIR)):
    if item not in sys.path:
        sys.path.insert(0, item)

from frontier30 import load_circuit
import sparse_backend
from validation.connected_quantum.corpus import (
    analytic_entangled_ghz_state,
    analytic_ghz_state,
    build_cases,
    build_sparse_analytic_cases,
    corpus_sha256,
    graph_is_connected,
)


class ConnectedCircuitCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = build_cases()

    def test_fixed_seed_corpus_is_reproducible(self):
        repeated = build_cases()
        self.assertEqual(corpus_sha256(self.cases), corpus_sha256(repeated))
        self.assertEqual([case["source_sha256"] for case in self.cases],
                         [case["source_sha256"] for case in repeated])
        self.assertEqual(len(self.cases), 24)

    def test_all_register_interaction_graphs_are_connected(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(graph_is_connected(
                    case["width"], case["entangling_edges"]
                ))

    def test_source_hash_and_ordered_gate_parse_match_corpus(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                raw = case["source"].encode("utf-8")
                self.assertEqual(hashlib.sha256(raw).hexdigest(),
                                 case["source_sha256"])
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "connected.sb"
                    path.write_bytes(raw)
                    circuit, source_hash = load_circuit(path)
                self.assertEqual(source_hash, case["source_sha256"])
                self.assertEqual(circuit.qubits, case["width"])
                self.assertEqual(circuit.gates,
                                 tuple(tuple(gate) for gate in case["gates"]))

    def test_exact_256_gate_limit_is_accepted_and_257th_is_rejected(self):
        case = next(case for case in self.cases
                    if case["kind"] == "adversarial-maximum-gate-budget")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "max-gates.sb"
            path.write_text(case["source"], encoding="utf-8", newline="\n")
            circuit, _ = load_circuit(path)
            self.assertEqual(len(circuit.gates), 256)
            path.write_text(
                "quantum too_many { qubits 2; "
                + " ".join("h 0;" for _ in range(257))
                + " measure_all; }\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(ValueError, "Gate limit exceeded"):
                load_circuit(path)

    def test_inverse_restores_vacuum_on_random_connected_case(self):
        case = self.cases[8]
        prefix_count = case["prefix_gate_count"]
        circuit = sparse_backend.Circuit(
            case["width"],
            tuple(tuple(gate) for gate in case["gates"]),
            case["id"],
        )
        state = sparse_backend.evolve(
            circuit,
            support_cap=1 << case["width"],
            memory_budget_bytes=64 * 1024 * 1024,
            max_seconds=20,
        )
        self.assertEqual(len(circuit.gates), 2 * prefix_count)
        self.assertAlmostEqual(state.get(0, 0j).real, 1.0, delta=1e-10)
        self.assertAlmostEqual(state.get(0, 0j).imag, 0.0, delta=1e-10)
        self.assertLess(max(
            (abs(value) for basis, value in state.items() if basis != 0),
            default=0.0,
        ), 1e-10)

    def test_connected_sparse_ghz_case_keeps_low_support(self):
        case = next(case for case in self.cases
                    if case["kind"] == "adversarial-connected-low-support")
        prefix = tuple(tuple(gate) for gate in case["gates"][:case["prefix_gate_count"]])
        circuit = sparse_backend.Circuit(case["width"], prefix, case["id"])
        stats = sparse_backend.EvolutionStats()
        state = sparse_backend.evolve(
            circuit,
            support_cap=64,
            memory_budget_bytes=64 * 1024 * 1024,
            max_seconds=5,
            stats=stats,
        )
        self.assertTrue(graph_is_connected(case["width"], case["entangling_edges"]))
        self.assertEqual(len(state), 4)
        self.assertLessEqual(stats.peak_support, 4)

    def test_connected_gate_graph_can_still_be_separable(self):
        case = next(case for case in self.cases
                    if case["kind"] == "adversarial-connected-but-separable")
        self.assertTrue(graph_is_connected(case["width"], case["entangling_edges"]))
        prefix = tuple(tuple(gate) for gate in case["gates"][:case["prefix_gate_count"]])
        state = sparse_backend.evolve(
            sparse_backend.Circuit(case["width"], prefix, case["id"]),
            support_cap=1 << case["width"],
            memory_budget_bytes=64 * 1024 * 1024,
            max_seconds=5,
        )
        angles = {gate[1]: gate[2] for gate in prefix if gate[0] == "rz"}
        expected = {}
        for basis in range(1 << case["width"]):
            amplitude = 1.0 / math.sqrt(1 << case["width"])
            for qubit, angle in angles.items():
                amplitude *= cmath.exp(
                    (1j if basis & (1 << qubit) else -1j) * angle / 2
                )
            expected[basis] = amplitude
        self.assertEqual(state.keys(), expected.keys())
        for basis in expected:
            self.assertAlmostEqual(abs(state[basis] - expected[basis]), 0.0,
                                   delta=1e-10)

    def test_connected_ghz_is_nonfactorizing_across_every_bipartition(self):
        width = 8
        gates = [("h", 0)]
        gates.extend(("cx", q, q + 1) for q in range(width - 1))
        state = sparse_backend.evolve(
            sparse_backend.Circuit(width, tuple(gates), "ghz-all-cuts"),
            support_cap=2,
            memory_budget_bytes=1024 * 1024,
            max_seconds=5,
        )
        expected = {0: 1 / math.sqrt(2), (1 << width) - 1: 1 / math.sqrt(2)}
        self.assertEqual(state.keys(), expected.keys())
        self.assertTrue(all(
            abs(state[basis] - amplitude) < 1e-12
            for basis, amplitude in expected.items()
        ))

        # Across each nontrivial cut, the all-zero and all-one branches occupy
        # two distinct rows and columns, so both Schmidt coefficients are 1/sqrt(2).
        for subset_mask in range(1, (1 << width) - 1):
            subset = [q for q in range(width) if subset_mask & (1 << q)]
            complement = [q for q in range(width) if q not in subset]
            self.assertTrue(subset and complement)
            self.assertEqual(len(subset), len(set(subset)))
            # The two GHZ branches have distinct A and B indices for every
            # proper cut, so the reduced spectrum is exactly (1/2, 1/2).
            zero_branch = (0, 0)
            one_branch = ((1 << len(complement)) - 1,
                          (1 << len(subset)) - 1)
            self.assertNotEqual(zero_branch[0], one_branch[0])
            self.assertNotEqual(zero_branch[1], one_branch[1])
            schmidt_probabilities = [
                abs(state[0]) ** 2,
                abs(state[(1 << width) - 1]) ** 2,
            ]
            purity = sum(value * value for value in schmidt_probabilities)
            rank = sum(value > 1e-12 for value in schmidt_probabilities)
            self.assertAlmostEqual(purity, 0.5, delta=1e-12)
            self.assertEqual(rank, 2)

    def test_dense_support_cap_refuses_before_expansion(self):
        circuit = sparse_backend.hadamard_support_adversary(13)
        with self.assertRaises(sparse_backend.ResourceLimitError) as caught:
            sparse_backend.evolve(
                circuit,
                support_cap=4096,
                memory_budget_bytes=64 * 1024 * 1024,
                max_seconds=5,
            )
        self.assertEqual(caught.exception.gate_index, 12)
        self.assertEqual(caught.exception.requested_support, 8192)

    def test_20_to_40_qubit_connected_ghz_matches_closed_form(self):
        for case in build_sparse_analytic_cases():
            with self.subTest(case=case["id"]):
                gates = tuple(tuple(gate) for gate in case["gates"])
                entangled_prefix = sparse_backend.evolve(
                    sparse_backend.Circuit(
                        case["width"],
                        gates[:case["entangled_ghz_gate_count"]],
                        case["id"] + "-ghz",
                    ),
                    support_cap=16,
                    memory_budget_bytes=1024 * 1024,
                    max_seconds=5,
                )
                expected_ghz = analytic_entangled_ghz_state(case)
                self.assertEqual(entangled_prefix.keys(), expected_ghz.keys())
                self.assertLess(max(
                    abs(entangled_prefix[basis] - expected_ghz[basis])
                    for basis in expected_ghz
                ), 1e-10)
                state = sparse_backend.evolve(
                    sparse_backend.Circuit(case["width"], gates, case["id"]),
                    support_cap=16,
                    memory_budget_bytes=1024 * 1024,
                    max_seconds=5,
                )
                expected = analytic_ghz_state(case)
                self.assertEqual(state.keys(), expected.keys())
                for basis in expected:
                    self.assertAlmostEqual(state[basis].real, expected[basis].real,
                                           delta=1e-10)
                    self.assertAlmostEqual(state[basis].imag, expected[basis].imag,
                                           delta=1e-10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
