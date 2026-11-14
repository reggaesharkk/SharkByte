# Public staging acceptance — SharkByte 0.2.1a2

This report preserves the exact-tree Windows ARM64 acceptance record for the earlier published MIT snapshot, before the current Apache-licensed and fixed-point-example changes. The original frozen source archive, wheel, and raw host security evidence are excluded and unchanged. It is not a claim that the current Apache-licensed revision has already passed that same local acceptance process.

## Exact-tree local acceptance
The staged package passed the isolated CI harness on Windows ARM64 / CPython 3.12.10. The run used a fresh virtual environment and pinned offline build wheelhouse while retaining PEP 517 build isolation. It removed PYTHONPATH/PYTHONHOME and user-site imports; the installed package was imported outside the checkout.

- 13/13 acceptance checks passed.
- Installed package source identity: 14/14 files matched.
- Regression tests: 30/30 in normal mode, 30/30 under -O, and 30/30 under -OO.
- Version, doctor, classical VM, quantum simulator, and bounded hybrid CLI smokes passed.
- Both native backends returned exit 1 with the exact containment-unavailable refusal and no stdout. These are negative native-disabled tests, not native functionality tests.
- Archived-vector replay covers 22 circuits / 320 probabilities. External Qiskit 2.6.2 evidence and provenance are scoped in QISKIT_PROVENANCE.md.

## Not verified by this run
- This report's Windows acceptance run did not cover later source changes.
- GitHub Actions for the earlier snapshot had not run when this report was first written.
- A fresh Ubuntu/aarch64 install of this exact curated tree had not been performed.
- Native execution, containment, and cancellation remain disabled/unverified.
- Vector replay reads archived Qiskit reference probabilities; it does not execute Qiskit.
- No physical quantum hardware was used.

## Hosted CI for the Apache-authorized source revision

Commit `bfe52efe568249f7d9c5dd0f5bc26dcbd132d624` passed [GitHub Actions run 43602167885](https://github.com/reggaesharkk/SharkByte/actions/runs/43602167885). All three jobs completed: Ubuntu and Windows Python 3.12 isolated install, acceptance, unit, and Frontier30 checks; plus Ubuntu 24.04 ARM64 backend agreement and execution-budget checks.

This hosted run does not replace the exact-tree Windows ARM64 acceptance above or establish NPU use, native host containment, physical-hardware execution, or a security sandbox. Later commits only update documentation records and manifest hashes. Raw local run logs are kept outside the public tree because they contain workstation paths. This is scoped acceptance evidence, not a release or RC1 claim.
