# SharkByte Lucid Dynamics v0.1 — experimental 4D ODE mode

This opt-in module implements the **dimensionless** four-state soft-wall ODE from [Bounded Self-Referential Dynamics, Appendix B v1.0](https://github.com/reggaesharkk/theory-of-bounded-existence). **It does not model human lucid dreaming, consciousness, real physical energy, cosmology, or quantum hardware.** The terms `lucid` and `Psi` are names for the model's mathematical parameters and memory state.

## Provenance and equations

- Mathematical source repository: `reggaesharkk/theory-of-bounded-existence`
- Pinned revision: `5bc839e6e0cf492882268d8ed47bef6ff82d65fc`
- Source: `verification_existence_v1_0.py`, `existence_4d_ode` and `launch_existence_sandbox.py`, `existence_4d_field`
- Initial state: `(gamma, H_obs, I_dot, Psi) = (2.05, 95, 4, 0.05)`
- `a=b=c=f=g=E_avail=1`, `e=3.6`, `I_erase=10`, `gamma_max=10`, `H_max=100`, `eps_H=eps_I=0.05`, `sigma_0=0.05`, `r_lrsc=1/9`, `mu_Psi=0.6`.

```text
P_eff = P_0 + lambda_sim * (1/9) * gamma + lambda_lucid * Psi
Hprime = gamma * (100-H_obs) - 10*tanh(H_obs/0.05)
fb = 3.6*tanh(I_dot/0.05)*Hprime
R_self = fb^2 / (fb^2 + P_0^2 + 0.05^2)
gamma' = I_dot*(1-gamma/10) - gamma
I_dot' = fb + P_eff - I_dot
Psi' = kappa_meta*R_self*(1-Psi) - 0.6*Psi
```

The term `Hprime` is the derivative of `H_obs`; the `I_dot'` expression is the derivative of the state named `I_dot`. The vector field uses Python `math.tanh` rather than NumPy's scalar `tanh`; this is the same mathematical function, with floating-point implementation differences possible.

## Run

From a SharkByte source checkout, first install the **optional** numerical extra:

```bash
python -m pip install -e '.[lucid]'
python -B sharkbyte_studio.py
```

Open `http://127.0.0.1:8120/lucid` or use the **Lucid Dynamics** link from the Studio home page. The ordinary SharkByte installation does **not** require NumPy or SciPy; existing VM and quantum routes are unchanged.

For headless local replay:

```bash
python -B -m sharkbyte_alpha.lucid_dynamics < examples/lucid_ivb.json > lucid-receipt.json
python -m unittest discover -s tests -p 'test_lucid*.py' -v
```

Regimes:

| Preset | P_0 | lambda_sim | lambda_lucid | kappa_meta | Expected behavior at 160 model units |
| --- | ---: | ---: | ---: | ---: | --- |
| `memoryless_collapse` | 0 | 7.2 | 0 | 2.5 | decay; no repeated late Poincaré crossings |
| `IVc_pure_psi_memory` | 0 | 0 | 0.3 | 2.5 | relaxation cycle, period ~17.936755 |
| `IVb_coupled_memory` | 0 | 7.2 | 0.3 | 2.5 | relaxation cycle, period ~19.387103 |

The periodicity diagnostic uses positive-direction intersections with the section `gamma = 2.0` in the second half of a finite forward integration. It does **not** prove periodic orbit existence, stability for arbitrary initial conditions, or a global attractor. For full variational/Floquet and boundary analysis use the upstream verification project; this module does not replicate that suite.

## Computational bounds and receipt meaning

- `P_0` 0–6, `lambda_sim` 0–10, `lambda_lucid` 0–1, `kappa_meta` 0–4.
- Duration 40–400 dimensionless units; 100–1600 output samples; fixed initial condition; fixed solver `LSODA`, `rtol=1e-9`, `atol=1e-12`, `max_step=0.5`.
- Studio requests are limited to 4096 input bytes, are validated by an allowlist, and execute in a separate Python subprocess subject to a 20-second timeout. This is an application-level bound, **not** OS-level CPU/memory containment or a security sandbox. The HTTP server remains bound to loopback and retains its local Host/Origin check.
- The JSON receipt includes source revision, exact parameters, numerical trace, observed Poincaré period if available, solver evaluation count, Python/NumPy/SciPy versions and SHA-256 of canonical JSON (excluding the hash field). SHA-256 checks integrity within an unchanged schema, **not** identity, authorship or mathematical correctness.
- Tests compare the vector field against an independent transcription, published benchmark periods, memoryless terminal decay, receipt tamper detection, DOP853 vs LSODA, invalid-input refusal, and local HTTP delivery.

Source remains preserved in its originating repository. Neither upstream manuscript nor SharkByte quantum execution is modified by this feature. Integrate only through a separately reviewed, **unmerged** feature branch.