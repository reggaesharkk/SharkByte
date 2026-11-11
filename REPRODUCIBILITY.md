# Reproducibility and provenance

This repository is a separately curated source tree for alpha 0.2.1a2. The previously accepted frozen source archive and wheel are excluded because the immutable archive contains personal-data disclosures in a report and nested evidence. No byte identity with those excluded artifacts is claimed.

Build uses pinned PEP 517 backend `setuptools==84.2.0`; runtime dependencies are empty. Install with `python -m pip install .` and leave build isolation enabled. `tools/ci_acceptance.py` installs into a fresh environment and tests from a separate fixture directory.

`tools/replay_qiskit_vectors.py` compares 22 circuits (320 probabilities) against separately accepted Qiskit 2.6.2 vectors. Tolerances: per-state absolute 1e-9; distribution L1 1e-8; normalization 1e-10. Bit order: q0 least significant, labels MSB-left, QASM `c[i]` measures `q[i]`.

The reference provenance is 0.2.2a1. Its `cli.py` and `quantum.py` hashes match this candidate; other package modules differ, so whole-package equivalence is not claimed. Raw host reports and the original nested archive are omitted; the checked-in fixtures/vectors are a sanitized subset, not the complete evidence packet.

SHA-256 proves identity/integrity, not correctness. Tests and numerical comparison are separate evidence. Gate 1/native containment remains unresolved and native execution remains disabled.
