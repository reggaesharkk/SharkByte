"""Adversarial regressions for the opt-in high-support scaling experiment."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from benchmarks.sb_quantum_benchmark.sparse_backend import evolve
from tools.high_support.frontier_scaling import (
    DEFAULT_MEMORY_MIB, _compaction_case, _json_hash, _run_case_worker,
    build_circuit, estimated_peak,
)
from tools.high_support.verify_frontier_scaling import (
    verify_receipt, _verify_compaction, _read_state,
    _state_hash as verifier_state_hash,
)


class FrontierScalingTests(unittest.TestCase):
    def test_low_support_and_connected_families_scale_without_register_allocation(self):
        for qubits in (12, 16, 20, 24, 28, 30):
            for family, cap, expected in (("basis-walk", 1, 1),
                                          ("connected-ghz", 2, 2),
                                          ("interference", 2, 1)):
                circuit = build_circuit(family, qubits, 991)
                state = evolve(circuit, support_cap=cap, memory_budget_bytes=cap*512)
                self.assertEqual(len(state), expected, (family, qubits))
                self.assertLess(estimated_peak(family, qubits)["combined_planning_bytes"],
                                DEFAULT_MEMORY_MIB * 1024 * 1024)

    def test_full_support_plan_refuses_before_24_qubit_allocations(self):
        cap = DEFAULT_MEMORY_MIB * 1024 * 1024
        for family in ("growing-support", "uncomputation", "dense-no-benefit"):
            self.assertLessEqual(estimated_peak(family, 20)["combined_planning_bytes"], cap)
            for qubits in (24, 28, 30):
                self.assertGreater(estimated_peak(family, qubits)["combined_planning_bytes"], cap)

    def test_exact_uncomputation_reduces_source_to_empty_but_dense_control_does_not(self):
        from frontier30 import simplify_inverses
        uncompute = build_circuit("uncomputation", 12, 1)
        optimized, pairs = simplify_inverses(uncompute)
        self.assertEqual(optimized.gates, ())
        self.assertEqual(len(pairs), len(uncompute.gates)//2)
        dense = build_circuit("dense-no-benefit", 12, 1)
        untouched, no_pairs = simplify_inverses(dense)
        self.assertEqual(untouched.gates, dense.gates)
        self.assertEqual(no_pairs, [])
        self.assertEqual(len(evolve(optimized, support_cap=1, memory_budget_bytes=512)), 1)

    def test_compaction_helpful_and_no_benefit_controls_replay_exactly(self):
        helpful = _compaction_case("helpful")
        no_benefit = _compaction_case("no-benefit")
        self.assertEqual(_verify_compaction(helpful)["status"], "PASS")
        self.assertEqual(_verify_compaction(no_benefit)["status"], "PASS")
        self.assertLess(helpful["compacted_support"], helpful["baseline_support"])
        self.assertEqual(no_benefit["compacted_support"], no_benefit["baseline_support"])
        self.assertLessEqual(Fraction(helpful["deletion_l2_bound"]), Fraction("1/100000000"))

    def test_forged_compaction_output_is_rejected_after_state_digest_is_recomputed(self):
        forged = copy.deepcopy(_compaction_case("helpful"))
        # Keep every outer digest internally consistent while substituting an
        # output amplitude. Exact certificate replay must still catch the forgery.
        basis, real, imag = forged["output_state"][0]
        forged["output_state"][0] = [basis, (float.fromhex(real) + 0.125).hex(), imag]
        forged["compacted_state_sha256"] = verifier_state_hash(
            {b: complex(float.fromhex(r), float.fromhex(i))
             for b, r, i in forged["output_state"]})
        with self.assertRaises(ValueError):
            _verify_compaction(forged)

    def test_receipt_state_decoder_rejects_duplicate_indices_and_noncanonical_hex(self):
        with self.assertRaises(ValueError):
            _read_state([[0, "0x1.0p+0", "0x0.0p+0"],
                         [0, "0x1.0p+1", "0x0.0p+0"]])
        with self.assertRaises(ValueError):
            _read_state([[0, "1.0", "0x0.0p+0"]])

    def test_source_bound_receipt_replay_and_hostile_hash_substitution(self):
        payload = _run_case_worker("basis-walk", 12, 73, 1, ("numpy",), 12)
        receipt = {"schema": "sharkbyte-frontier-scaling-v1", "decision": "PASS",
                   "configuration": {"worker_memory_limit_bytes": 1024**3,
                                     "full_reference_qubits": 12, "repeats": 1},
                   "source_sha256": _current_hashes(),
                   "cases": [{"family": "basis-walk", "qubits": 12,
                              "status": "PASS", "resource_plan": {}, "payload": payload}]}
        receipt["record_sha256"] = _json_hash(receipt)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertEqual(verify_receipt(path, required_backends=("numpy",))["status"], "PASS")
            forged = copy.deepcopy(receipt)
            forged["cases"][0]["payload"]["repetitions"][0]["state_sha256"] = "0"*64
            unsigned = dict(forged)
            unsigned.pop("record_sha256")
            forged["record_sha256"] = _json_hash(unsigned)
            path.write_text(json.dumps(forged), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_receipt(path, required_backends=("numpy",))
            substituted = copy.deepcopy(receipt)
            substituted["source_sha256"]["tools/high_support/frontier_scaling.py"] = "0"*64
            unsigned = dict(substituted)
            unsigned.pop("record_sha256")
            substituted["record_sha256"] = _json_hash(unsigned)
            path.write_text(json.dumps(substituted), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_receipt(path)
            resealed_gates = copy.deepcopy(receipt)
            repetition = resealed_gates["cases"][0]["payload"]["repetitions"][0]
            repetition["gates"][0] = ["x", 0]
            repetition["circuit_sha256"] = _json_hash({
                "qubits": 12, "gates": repetition["gates"]})
            unsigned = dict(resealed_gates)
            unsigned.pop("record_sha256")
            resealed_gates["record_sha256"] = _json_hash(unsigned)
            path.write_text(json.dumps(resealed_gates), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_receipt(path)


def _current_hashes():
    from tools.high_support.frontier_scaling import _source_hashes
    return _source_hashes()


if __name__ == "__main__":
    unittest.main()
