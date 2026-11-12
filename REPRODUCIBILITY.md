# Reproducibility and provenance

This repository is a separately curated source tree for alpha 0.2.1a2. The previously accepted frozen source archive and wheel are excluded because the immutable archive contains personal-data disclosures in a report and nested evidence. No byte identity with those excluded artifacts is claimed.

Build uses the pinned PEP 517 backend `setuptools==84.2.0`; runtime dependencies are empty. Install with `python -m pip install .` and leave build isolation enabled. For offline builds, use the pinned wheelhouse procedure in `INSTALL.md`; do not disable PEP 517 isolation. `tools/ci_acceptance.py` installs into a fresh environment and tests from a separate fixture directory.

`tools/replay_qiskit_vectors.py` compares 22 circuits (320 probabilities) against separately accepted Qiskit 2.6.2 vectors. Tolerances: per-state absolute 1e-9; distribution L1 1e-8; normalization 1e-10. Bit order: q0 least significant, labels MSB-left, QASM `c[i]` measures `q[i]`.

The reference provenance is 0.2.2a1. Its `cli.py` and `quantum.py` hashes match this candidate; other package modules differ, so whole-package equivalence is not claimed. Raw host reports and the original nested archive are omitted; the checked-in fixtures/vectors are a sanitized subset, not the complete evidence packet.

The authorized Ubuntu reproducibility run (2026-11-12) built the source archive twice and the wheel twice in isolated builds. Each pair was byte-identical: sdist 73,613 bytes, SHA-256 `c6f12d85852e06198f053607d7b8f6a7b573dad94ab993271b7e24ff2e57a7c4`; wheel 52,748 bytes, SHA-256 `2eedac9921b62ae23cd8674e8b12a829aa0576e8e6a73af1c3e0e43dbafd8c9f`. The full host report and its 476-entry manifest readback are summarized in [the dated addendum](docs/UBUNTU_REPRODUCIBILITY_ADDENDUM_20261112.md). Windows ARM64 fresh-install regression evidence is separate and is not claimed as a second-host archive reproducibility comparison.

SHA-256 proves identity/integrity, not correctness. Tests and numerical comparison are separate evidence. Gate 1/native containment remains unresolved and native execution remains disabled.
