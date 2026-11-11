# Public staging acceptance - SharkByte 0.2.1a2

This report covers the curated source tree prepared for the public repository. The original frozen source archive, wheel, and raw host security evidence are excluded and unchanged.

## Exact-tree local acceptance
The staged package passed the isolated CI harness on Windows ARM64 / CPython 3.12.10. The run used a fresh virtual environment and pinned offline build wheelhouse while retaining PEP 517 build isolation. It removed PYTHONPATH/PYTHONHOME and user-site imports; the installed package was imported outside the checkout.

- 13/13 acceptance checks passed.
- Installed package source identity: 14/14 files matched.
- Regression tests: 30/30 in normal mode, 30/30 under -O, and 30/30 under -OO.
- Version, doctor, classical VM, quantum simulator, and bounded hybrid CLI smokes passed.
- Both native backends returned exit 1 with the exact containment-unavailable refusal and no stdout. These are negative native-disabled tests, not native functionality tests.
- Archived-vector replay covers 22 circuits / 320 probabilities. External Qiskit 2.6.2 evidence and provenance are scoped in QISKIT_PROVENANCE.md.

## Not verified by this run
- GitHub Actions had not run.
- A fresh Ubuntu/aarch64 install of this exact curated tree had not been performed.
- Native execution, containment, and cancellation remain disabled/unverified.
- Vector replay reads archived Qiskit reference probabilities; it does not execute Qiskit.
- No physical quantum hardware was used.

Raw local run logs are kept outside the public tree because they contain workstation paths. This is a scoped local report, not a release or RC1 claim.
