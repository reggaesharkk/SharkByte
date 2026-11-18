# Independent receipt audit · Windows ARM64 submissions

Nine uploaded records contain five numerical experiments. All reported canonical SHA-256 digests recomputed exactly after removing only `record_sha256` and serializing sorted UTF-8 JSON with compact separators. Python 3.12.10, NumPy 2.5.5 and SciPy 1.18.1 are recorded environment metadata. The hashes establish internal integrity.

| File ID prefix | Selected preset | Effective configuration | Duration | Last period | Terminal norm | Verified canonical SHA-256 |
|---|---|---|---:|---:|---:|---|
| 02f305ce | IVc | Zero corner | 40 | — | 1.89774e-12 | `e578c54dee51209b9f2f4cb1680898d07d3d849d9b3ab9544c73de08bc46675b` |
| 19f1b255 | IVb | Zero corner | 40 | — | 1.89774e-12 | `1157317a389e32e846a82d979045d131a9689b2d266303060a7170e36ebac404` |
| 2279bd88 | IVc | IVc | 160 | 17.936754796907792 | 113.3347 | `556f28cba56a40195cd4931b63e7825579e6312366a88a2c56651929117eb98c` |
| 3657563e | IVb | IVb | 160 | 19.38710319306651 | 93.68666 | `937159c637caf63d273ce42d5e08965fbdda0e0144363402ec1b43b604d79dff` |
| 47113b52 | IVc | Maximum corner | 400 | — | 99.06351 | `8a4177a34f18114285ab8cb463817e3b586555e09e3e326b2c3d3dd1437a2d64` |
| a2f22fe5 | IVb | Maximum corner | 400 | — | 99.06351 | `60c62ad3e05cdf80c42b1411ace7f218b179c7de173d103777ddaf5bca4d04e7` |
| aac0c767 | memoryless | Maximum corner | 400 | — | 99.06351 | `163c986a69d640158e9c3423263e3fb3949faa37145fb246604e82ca0b843662` |
| b08efe75 | memoryless | memoryless | 160 | — | 4.232941e-12 | `5ac8599160a6a18e87b289fe6555845871e29dfbf4a148368bc6f3e8003536d3` |
| c2d920fc | memoryless | Zero corner | 40 | — | 1.89774e-12 | `8a43e135da906abdfe6005dc8d459fa758e791a196d0c7fb3e9d66957ab31069` |

Parameter order is P₀, λ_sim, λ_lucid, κ_meta. The zero corner is (0,0,0,0) and the maximum corner is (6,10,1,4). Each corner has three identical full result payloads under different starting labels. The source memoryless ablation retains proportional feedback and Ψ formation at (0,7.2,0,2.5). IVb uses (0,7.2,0.3,2.5) and IVc uses (0,0,0.3,2.5).

## Numerical cross-check

At source revision [5bc839e](https://github.com/reggaesharkk/theory-of-bounded-existence/blob/5bc839e6e0cf492882268d8ed47bef6ff82d65fc/verification_existence_v1_0.py), the four derivatives and constants agree term by term. The Studio uses scalar math.tanh. All receipts used LSODA at relative tolerance 1e-9, absolute tolerance 1e-12 and maximum step 0.5 from (2.05,95,4,0.05). Reintegrating the upstream Python field with implicit Radau at 1e-10, 1e-13 and maximum step 0.25 reproduced all late upward γ=2 event times within 1e-5. Maximum absolute coordinate differences across the saved time grids were 5.59e-5 (IVc), 1.57e-5 (IVb), 2.34e-7 (memoryless), 1.16e-7 (zero corner) and 1.46e-8 (maximum corner).

Every trajectory had the expected four channels and sampling grid. All values were finite. The recorded tail spans and final norms recomputed from the samples. Sampled γ, H_obs and Ψ respected their source box bounds within 1e-8; small negative numerical residues occurred near zero. IVc reached sampled I_dot about 265, illustrating why a shared vertical scale would obscure Ψ. The two measured periods agree with the rounded source periods to about 2.1e-7. None of these finite-time observations establishes a global attractor or a physiological interpretation. Absence of two late crossings alone does not establish convergence to an equilibrium.

Reproduce the checks with `python -m unittest discover -s tests -p "test_lucid*.py" -v`. For the independent comparison use the uploaded JSONs, the pinned source module on PYTHONPATH, and run `python -m tools.audit_lucid_receipts DIRECTORY` with NumPy, SciPy, SymPy and mpmath installed.
