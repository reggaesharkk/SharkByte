"""Automated unit tests for the independent live-Qiskit validation suite."""
import importlib.util
import unittest

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
