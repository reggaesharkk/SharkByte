# Reproducibility and provenance

This repository is a separately curated source tree for alpha 0.2.1a2. The previously accepted frozen source archive and wheel are excluded because the immutable archive contains personal-data disclosures in a report and nested evidence. No byte identity with those excluded artifacts is claimed.

Build uses pinned PEP 517 backend `setuptools==84.2.0`; runtime dependencies are empty. Install with `python -m pip install .` and leave build isolation enabled. `tools/ci_acceptance.py` installs into a fresh environment and tests from a separate fixture directory.

`tools/replay_qiskit_vectors.py` compares 22 circuits (320 probabilities) against separately accepted Qiskit 2.6.2 vectors. Tolerances: per-state absolute 1e-9; distribution L1 1e-8; normalization 1e-10. Bit order: q0 least significant, labels MSB-left, QASM `c[i]` measures `q[i]`.

The opt-in adaptive CLI packet under `evidence/adaptive-cli-cross-platform-20261118/` preserves three original Windows ARM64 and three Ubuntu WSL2 ARM64 run receipts. Run `python -B tools/verify_adaptive_cli_acceptance.py --receipt-dir <platform-receipt-directory> --output <report.json>` from the repository root to verify embedded source/record hashes and deterministically replay the three CLI cases on the current host. The verifier requires exact source-fixture matches, the dense transition at gate 16/support 65,536, and the 1 MiB refusal at gate 10 with exit code 1. Its one-run wall times are replay diagnostics, not benchmark measurements; use `tools/high_support/benchmark_adaptive.py` and its separate seven-repetition evidence for performance.

The reference provenance is 0.2.2a1. The historical CLI and quantum source fixtures preserve its module hashes. The current source has evolved since those fixtures were recorded. Raw host reports and the original nested archive are omitted; the checked-in fixtures/vectors are a sanitized subset, not the complete evidence packet.

SHA-256 proves identity/integrity, not correctness. Tests and numerical comparison are separate evidence. Gate 1/native containment remains unresolved and native execution remains disabled.


The web/app DSL compiler is deterministic for the checked-in project source and environment-independent generated files. Rebuild examples with `python -m sharkbyte_alpha web build examples/web/research-portfolio` and `python -m sharkbyte_alpha app build examples/web/interactive-dashboard` / `... task-app`. Run `python -m unittest tests.test_web_builder -v` for DSL and Studio endpoint regressions. These checks do not yet include a browser engine automation run.
