"""Scoped integration/regression tests for the opt-in, dimensionless Lucid Dynamics mode."""
import json
import importlib.util
import math
import subprocess
import sys
import unittest
from pathlib import Path

from sharkbyte_alpha.lucid_dynamics import (
    INITIAL_STATE, PRESETS, field, simulate, validate_request, verify_receipt,
)


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Lucid numerical extra (NumPy + SciPy) is not installed")
class LucidDynamicsTests(unittest.TestCase):
    def test_field_independent_reference(self):
        # Direct transcription of upstream launch_existence_sandbox.py numerical field.
        gamma, h, i, psi = (2.05, 95.0, 4.0, 0.05)
        p0, lsim, lluc, kap = 0.0, 7.2, .3, 2.5
        dh = gamma * (100 - h) - 10 * math.tanh(h / .05)
        fb = 3.6 * math.tanh(i / .05) * dh
        rs = fb**2 / (fb**2 + p0**2 + .05**2)
        expected = [i * (1 - gamma / 10) - gamma, dh,
                    fb + p0 + lsim / 9 * gamma + lluc * psi - i,
                    kap * rs * (1 - psi) - .60 * psi]
        got = field(0., INITIAL_STATE, P_0=p0, lambda_sim=lsim,
                    lambda_lucid=lluc, kappa_meta=kap)
        for a, b in zip(got, expected):
            self.assertAlmostEqual(a, b, delta=1e-12)

    def test_reject_invalid_and_unbounded_requests(self):
        invalid = [None, [], {"preset": "wat"}, {"preset": "__class__"},
                   {"parameters": {"P_0": float("nan")}},
                   {"parameters": {"lambda_lucid": 999}},
                   {"parameters": {"lambda_sim": True}},
                   {"parameters": {"evil": 1}},
                   {"duration": -1}, {"duration": 401}, {"duration": float("inf")},
                   {"duration": True}, {"samples": 99}, {"samples": 1601},
                   {"samples": 500.0}, {"unexpected": "execute this"}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_request(value)

    def test_exact_three_presets_and_reproducible_hashes(self):
        expected = {"memoryless_collapse": (False, None),
                    "IVc_pure_psi_memory": (True, 17.936755),
                    "IVb_coupled_memory": (True, 19.387103)}
        for preset in PRESETS:
            with self.subTest(preset=preset):
                rec = simulate({"preset": preset, "duration": 160, "samples": 300})
                self.assertTrue(verify_receipt(rec))
                d = rec["result"]["diagnostics"]
                self.assertEqual(d["cycle_observed"], expected[preset][0])
                if expected[preset][1] is not None:
                    self.assertAlmostEqual(d["observed_period"], expected[preset][1], delta=0.001)
                self.assertEqual(rec["result"]["t"][0], 0.0)
                self.assertEqual(len(rec["result"]["Psi"]), 300)
                self.assertGreaterEqual(min(rec["result"]["Psi"]), -1e-9)
                self.assertLessEqual(max(rec["result"]["Psi"]), 1 + 1e-9)
                changed = json.loads(json.dumps(rec))
                changed["result"]["Psi"][7] += 0.5
                self.assertFalse(verify_receipt(changed))
                again = simulate({"preset": preset, "duration": 160, "samples": 300})
                self.assertEqual(again["record_sha256"], rec["record_sha256"])

    def test_memoryless_decay_at_400_and_solver_crosscheck(self):
        from scipy.integrate import solve_ivp
        rec = simulate({"preset": "memoryless_collapse", "duration": 400, "samples": 400})
        self.assertLess(rec["result"]["diagnostics"]["final_state_norm"], 1e-10)
        p = PRESETS["IVc_pure_psi_memory"]
        other = solve_ivp(lambda t, y: field(t, y, **p), (0, 160), INITIAL_STATE,
                          method="DOP853", rtol=2e-10, atol=2e-13, max_step=.2)
        self.assertTrue(other.success)
        lsoda = simulate({"preset": "IVc_pure_psi_memory", "duration": 160, "samples": 300})
        # phase error after many sharp relaxation pulses may amplify, compare to 1e-3.
        for i, key in enumerate(("gamma", "H_obs", "I_dot", "Psi")):
            self.assertAlmostEqual(other.y[i, -1], lsoda["result"][key][-1], delta=0.04)

    def test_stdin_json_worker(self):
        proc = subprocess.run([sys.executable, "-B", "-m", "sharkbyte_alpha.lucid_dynamics"],
                              input=json.dumps({"preset": "memoryless_collapse", "samples": 100}),
                              text=True, capture_output=True, timeout=20,
                              cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(verify_receipt(json.loads(proc.stdout)))
        refused = subprocess.run([sys.executable, "-B", "-m", "sharkbyte_alpha.lucid_dynamics"],
                                 input='{"samples":999999}', text=True,
                                 capture_output=True, timeout=10,
                                 cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(refused.stdout, "")


if __name__ == "__main__":
    unittest.main()