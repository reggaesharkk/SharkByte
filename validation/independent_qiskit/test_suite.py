"""Automated unit tests for the independent live-Qiskit validation suite."""
from dataclasses import replace
import importlib.util
import unittest
from unittest.mock import patch

from validation.independent_qiskit import suite


@unittest.skipUnless(importlib.util.find_spec("qiskit"),
                     "optional Qiskit dependency is installed by the scoped validation workflow")
class LiveQiskitValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = suite.run_validations()
        cls.sections = cls.report["sections"]

    def test_at_least_100_seeded_circuits_compare_live_statevectors(self):
        result = self.sections["randomized_live_statevector"]
        self.assertEqual(result["status"], "PASS", result.get("summary", result))
        self.assertGreaterEqual(result["summary"]["circuits"], 100)
        self.assertEqual(result["summary"]["gate_coverage"], sorted(suite.SUPPORTED_GATES))
        self.assertTrue(result["summary"]["deterministic_replay"])
        self.assertTrue(all(case["status"] == "PASS" for case in result["cases"]))

    def test_gate_inverses(self):
        self.assertEqual(self.sections["gate_inverses"]["status"], "PASS",
                         self.sections["gate_inverses"])
        self.assertEqual(self.sections["gate_inverses"]["summary"]["inverse_pairs"], 8)

    def test_interference(self):
        self.assertEqual(self.sections["interference"]["status"], "PASS",
                         self.sections["interference"])

    def test_controlled_phase_direction_and_target(self):
        self.assertEqual(self.sections["controlled_phase"]["status"], "PASS",
                         self.sections["controlled_phase"])
        self.assertEqual(self.sections["controlled_phase"]["summary"]["ordered_control_target_pairs"], 6)

    def test_numerical_boundaries(self):
        self.assertEqual(self.sections["numerical_boundaries"]["status"], "PASS",
                         self.sections["numerical_boundaries"])

    def test_bit_ordering(self):
        self.assertEqual(self.sections["bit_ordering"]["status"], "PASS",
                         self.sections["bit_ordering"])

    def test_global_phase_is_removed_before_amplitude_comparison(self):
        self.assertEqual(self.sections["global_phase_alignment"]["status"], "PASS",
                         self.sections["global_phase_alignment"])

    def test_sparse_and_dense_simulators_agree(self):
        self.assertEqual(self.sections["sparse_dense_agreement"]["status"], "PASS",
                         self.sections["sparse_dense_agreement"])
        self.assertEqual(self.sections["sparse_dense_agreement"]["circuits_compared"],
                         suite.RANDOM_CIRCUIT_COUNT)


    def test_incorrect_register_width_is_rejected(self):
        gates = [("x", 0)]
        source = suite.render_program(2, gates, 42)
        with self.assertRaisesRegex(ValueError, "reported 2 qubits, expected 3"):
            suite._evaluate_source(source, 42, 3, gates)

    def test_wrong_sparse_angle_sign_fails(self):
        gates = [("ry", 0, 0.75), ("h", 0)]
        source = suite.render_program(1, gates, 42)
        original = suite.load_circuit

        def flipped_angle(path):
            circuit, digest = original(path)
            return replace(circuit, gates=(("ry", 0, -0.75), circuit.gates[1])), digest

        with patch.object(suite, "load_circuit", flipped_angle):
            result = suite._evaluate_source(source, 42, 1, gates)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["checks"]["frontier_source_matches_canonical"])
        self.assertFalse(result["checks"]["sparse_dense_probabilities"])

    def test_incorrect_dense_rotation_matrix_fails(self):
        gates = [("rx", 0, 0.75)]
        source = suite.render_program(1, gates, 42)
        original = suite.quantum.simulate

        def wrong_matrix_element(circuit):
            state = original(circuit)
            # Substitute the real RY coefficient for RX's imaginary coefficient.
            state[1] *= 1j
            return state

        with patch.object(suite.quantum, "simulate", wrong_matrix_element):
            result = suite._evaluate_source(source, 42, 1, gates)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["probabilities"])
        self.assertTrue(result["checks"]["state_normalization"])
        self.assertFalse(result["checks"]["global_phase_aligned_amplitudes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
