"""Opt-in, bounded 4D soft-wall ODE replay for SharkByte Studio.

Mathematical source: reggaesharkk/theory-of-bounded-existence,
commit 5bc839e6e0cf492882268d8ed47bef6ff82d65fc,
verification_existence_v1_0.py:171-185 / launch_existence_sandbox.py:22-38.
Dimensionless ODE only; Psi is a model state, not a measured dream state.
SciPy is an OPTIONAL dependency: ordinary SharkByte execution stays dependency-free.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from typing import Any

SOURCE_REPO = "reggaesharkk/theory-of-bounded-existence"
SOURCE_COMMIT = "5bc839e6e0cf492882268d8ed47bef6ff82d65fc"
SOURCE_PATH = "verification_existence_v1_0.py"
INITIAL_STATE = (2.05, 95.0, 4.0, 0.05)
PARAMETERS = {
    "a": 1.0, "b": 1.0, "c": 1.0, "e": 3.60,
    "f": 1.0, "g": 1.0, "E_avail": 1.0,
    "I_erase": 10.0, "gamma_max": 10.0, "H_max": 100.0,
    "eps_H": 0.05, "eps_I": 0.05, "sigma_0": 0.05,
    "r_lrsc": 1.0 / 9.0, "mu_Psi": 0.60,
}
PRESETS = {
    "memoryless_collapse": {"P_0": 0.0, "lambda_sim": 7.20, "lambda_lucid": 0.0, "kappa_meta": 2.50},
    "IVc_pure_psi_memory": {"P_0": 0.0, "lambda_sim": 0.0, "lambda_lucid": 0.30, "kappa_meta": 2.50},
    "IVb_coupled_memory": {"P_0": 0.0, "lambda_sim": 7.20, "lambda_lucid": 0.30, "kappa_meta": 2.50},
}
LIMITS = {"P_0": (0.0, 6.0), "lambda_sim": (0.0, 10.0),
          "lambda_lucid": (0.0, 1.0), "kappa_meta": (0.0, 4.0)}


def field(t: float, y: tuple[float, ...], *, P_0: float,
          lambda_sim: float, lambda_lucid: float, kappa_meta: float) -> list[float]:
    """Exact source equations and constants, with stdlib tanh replacing NumPy scalar tanh."""
    gamma, H_obs, I_dot, Psi = y
    p = PARAMETERS
    P_eff = P_0 + lambda_sim * p["r_lrsc"] * gamma + lambda_lucid * Psi
    dgamma = p["a"] * I_dot * p["E_avail"] * (1.0 - gamma / p["gamma_max"]) - p["b"] * gamma
    dHobs = p["c"] * gamma * (p["H_max"] - H_obs) - p["I_erase"] * math.tanh(H_obs / p["eps_H"])
    fb = p["e"] * math.tanh(I_dot / p["eps_I"]) * dHobs
    dIdot = fb + p["f"] * P_eff - p["g"] * I_dot
    R_self = (fb * fb) / (fb * fb + (p["f"] * P_0) ** 2 + p["sigma_0"] ** 2)
    dPsi = kappa_meta * R_self * (1.0 - Psi) - p["mu_Psi"] * Psi
    return [dgamma, dHobs, dIdot, dPsi]


def validate_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("A JSON object is required.")
    if set(request) - {"preset", "parameters", "duration", "samples"}:
        raise ValueError("Unknown request field.")
    preset = request.get("preset", "IVb_coupled_memory")
    if not isinstance(preset, str) or preset not in PRESETS:
        raise ValueError("Unknown Lucid Dynamics preset.")
    overrides = request.get("parameters", {})
    if not isinstance(overrides, dict) or set(overrides) - set(LIMITS):
        raise ValueError("Invalid parameter names.")
    params = dict(PRESETS[preset])
    for name, val in overrides.items():
        low, high = LIMITS[name]
        if isinstance(val, bool) or not isinstance(val, (float, int)) or not low <= val <= high:
            raise ValueError(f"{name} must be finite and between {low} and {high}.")
        params[name] = float(val)
    duration = request.get("duration", 160)
    samples = request.get("samples", 600)
    if type(duration) not in (int, float) or not 40 <= duration <= 400:
        raise ValueError("duration must be in [40, 400] model time units.")
    if type(samples) is not int or not 100 <= samples <= 1600:
        raise ValueError("samples must be an integer in [100, 1600].")
    return {"preset": preset, "parameters": params, "duration": float(duration), "samples": samples}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode("utf-8")


def verify_receipt(receipt: dict[str, Any]) -> bool:
    if not isinstance(receipt, dict) or not isinstance(receipt.get("record_sha256"), str):
        return False
    copy = dict(receipt)
    recorded = copy.pop("record_sha256")
    try:
        return hashlib.sha256(_canonical(copy)).hexdigest() == recorded
    except (ValueError, TypeError, OverflowError):
        return False


def simulate(request: Any) -> dict[str, Any]:
    """Numerical replay, not a theorem prover or evidence of physiological lucid dreaming."""
    import numpy as np
    from scipy.integrate import solve_ivp
    import scipy

    cfg = validate_request(request)
    params = cfg["parameters"]
    duration = cfg["duration"]
    t_eval = np.linspace(0.0, duration, cfg["samples"])

    def ode(t, y):
        return field(t, y, **params)

    def poincare(t, y):
        return y[0] - 2.0
    poincare.direction = 1
    poincare.terminal = False

    sol = solve_ivp(ode, (0.0, duration), INITIAL_STATE, method="LSODA",
                    t_eval=t_eval, rtol=1e-9, atol=1e-12,
                    events=poincare, max_step=0.5)
    if not sol.success or sol.y.shape != (4, cfg["samples"]) or not np.isfinite(sol.y).all():
        raise RuntimeError("ODE solver failed or returned nonfinite state.")
    crossings = [float(t) for t in sol.t_events[0] if t >= duration / 2]
    cycle_period = float(crossings[-1] - crossings[-2]) if len(crossings) >= 2 else None
    trajectory = {name: [float(v) for v in sol.y[i]]
                  for i, name in enumerate(("gamma", "H_obs", "I_dot", "Psi"))}
    tail = sol.y[:, t_eval >= (0.8 * duration)]
    tail_span = {name: float(np.ptp(tail[i])) for i, name in enumerate(trajectory)}
    final_norm = float(np.linalg.norm(sol.y[:, -1]))
    effective = next((name for name, values in PRESETS.items() if params == values), "custom")
    reference = {"IVc_pure_psi_memory": 17.936755, "IVb_coupled_memory": 19.387103}.get(effective)
    receipt = {
        "schema": "sharkbyte.lucid-dynamics.v0.1", "mode": "lucid_dynamics",
        "source": {"repository": SOURCE_REPO, "commit": SOURCE_COMMIT, "path": SOURCE_PATH,
                   "note": "4D soft-wall ODE, dimensionless toy model"},
        "config": {**cfg, "effective_regime": effective, "initial_state": list(INITIAL_STATE),
                   "model_constants": PARAMETERS,
                   "solver": {"method": "LSODA", "rtol": 1e-9, "atol": 1e-12, "max_step": 0.5}},
        "runtime": {"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "numpy": np.__version__, "scipy": scipy.__version__},
        "result": {"t": [float(v) for v in sol.t], **trajectory,
                   "diagnostics": {"solver_success": True, "nfev": int(sol.nfev),
                                   "final_state_norm": final_norm, "tail_range": tail_span,
                                   "poincare_upcrossings_in_second_half": crossings,
                                   "observed_period": cycle_period, "reference_period": reference,
                                   "period_difference": cycle_period - reference if cycle_period is not None and reference is not None else None,
                                   "cycle_observed": bool(cycle_period is not None),
                                   "cycle_interpretation": "Finite-time Poincare observation, not global existence proof"}},
        "claims": {"scientific_scope": "dimensionless 4D toy ODE only",
                   "no_physiology_or_cosmology": True,
                   "numerical_not_formal_proof": True},
    }
    receipt["record_sha256"] = hashlib.sha256(_canonical(receipt)).hexdigest()
    return receipt


def main() -> int:
    try:
        request = json.load(sys.stdin)
        # Ensure parse/trailing data is handled by json.load.
        receipt = simulate(request)
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return 0
    except (ValueError, RuntimeError, ImportError) as exc:
        print(f"Lucid Dynamics error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())