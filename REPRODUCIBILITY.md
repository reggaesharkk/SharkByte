# Reproducibility and provenance

This repository is a separately curated source tree for alpha 0.2.1a2. The previously accepted frozen source archive and wheel are excluded because the immutable archive contains personal-data disclosures in a report and nested evidence. No byte identity with those excluded artifacts is claimed.

Build uses the pinned PEP 517 backend `setuptools==84.2.0`; runtime dependencies are empty. Install with `python -m pip install .` and leave build isolation enabled. For offline builds, use the pinned wheelhouse procedure in `INSTALL.md`; do not disable PEP 517 isolation. `tools/ci_acceptance.py` installs into a fresh environment and tests from a separate fixture directory.

`tools/replay_qiskit_vectors.py` compares 22 circuits (320 probabilities) against separately accepted Qiskit 2.6.2 vectors. Tolerances: per-state absolute 1e-9; distribution L1 1e-8; normalization 1e-10. Bit order: q0 least significant, labels MSB-left, QASM `c[i]` measures `q[i]`.

The reference provenance is 0.2.2a1. Its `cli.py` and `quantum.py` hashes match this candidate; other package modules differ, so whole-package equivalence is not claimed. Raw host reports and the original nested archive are omitted; the checked-in fixtures/vectors are a sanitized subset, not the complete evidence packet.

The first Ubuntu reproducibility run (2026-11-12) built an earlier source state twice and recorded 476 manifest entries; its artifact hashes remain in the dated addendum as historical evidence. A later authorized Ubuntu/aarch64 run verified a 496-entry manifest and two byte-identical source archives and wheels for the exact worktree identity recorded there. It also installed from the extracted source archive and passed the scoped smoke and regression checks. This worktree had Git HEAD `8a9ace7ccac7f9cb491604350006273cf256c196` plus uncommitted changes; its test result therefore does not assert reproducibility for that commit alone or for later branch commits. See [the dated addendum](docs/UBUNTU_REPRODUCIBILITY_ADDENDUM_20261112.md) for both runs and exact artifact hashes. Windows ARM64 install/regression evidence is separate and is not a second-host archive reproducibility comparison.

SHA-256 proves identity/integrity, not correctness. Tests and numerical comparison are separate evidence. Gate 1/native containment remains unresolved and native execution remains disabled.
