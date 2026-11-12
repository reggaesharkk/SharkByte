# SharkByte standalone alpha 0.2.1a2

A separately curated, source-only public snapshot of a bounded experimental language toolchain. It includes an installable Python CLI, SharkVM, classical statevector simulator, bounded hybrid orchestration, examples, tests, and a scoped independent Qiskit reference fixture set.

## Supported functionality
- Classical SharkVM execution with a 100,000-instruction limit.
- Classical CPU statevector simulation for the documented quantum subset.
- Bounded hybrid execution with measurement feedback and limited adaptive updates.
- OpenQASM 3 output for the documented subset.
- SHA-256 receipt integrity checking; hashes do not authenticate a record.

Native interpreter and Direct AArch64 backends are disabled and refuse before launching native code. Quantum circuits run in a classical simulator; no physical quantum hardware is used. SharkVM is not a security sandbox.

The included Qiskit fixture subset covers 22 circuits / 320 probabilities and uses separately accepted Qiskit 2.6.2 reference results with 0.2.2a1 quantum provenance. Only specified modules match this candidate; no whole-package identity is claimed. See QISKIT_PROVENANCE.md.

## Install
Requires CPython 3.10+ and pip; runtime dependencies are empty. PEP 517 build isolation is enabled, with setuptools==84.2.0 pinned in pyproject.toml.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Ubuntu/macOS:      . .venv/bin/activate
python -m pip install .
sharkbyte --version
sharkbyte doctor
```

For offline installation, download the pinned build requirements and dependencies on a connected machine, then transfer the wheelhouse:
```sh
python -m pip download --only-binary=:all: --dest build-wheelhouse -r BUILD_REQUIREMENTS.txt
python -m pip install --no-index --find-links build-wheelhouse .
```
Keep pip's normal build isolation enabled. See INSTALL.md.

## Examples
```sh
sharkbyte run examples/example.sb --backend vm
sharkbyte run examples/bell.sb --mode quantum
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm
sharkbyte qasm examples/bell.sb --output bell.qasm
sharkbyte verify-run result.json
```

Run python tools/ci_acceptance.py for isolated install and regressions. python tools/replay_qiskit_vectors.py compares archived reference values; it does not invoke Qiskit.

See PUBLIC_STAGE_ACCEPTANCE.md for exact-tree test scope and `docs/PUBLIC_QISKIT_REPLAY_ADDENDUM_20261112.md` for the later dated evidence. As of 2026-11-12, GitHub Actions passed on its hosted Ubuntu and Windows runners, and user-hosted acceptance was reported on Windows ARM64 and Ubuntu aarch64. A direct Qiskit replay on the exact public commit `95f936aa32e10ee8ef726093889067086e4c4421` reported 22 circuits / 320 probabilities passing the documented distribution tolerances. Its auxiliary statevector-norm diagnostic emitted a `ComplexWarning` and is explicitly caveated in the addendum; the distribution replay is complete, while no warning-free norm-diagnostic rerun is claimed. Hosted runner architecture is not asserted to be ARM64.

This curated source tree is licensed under Apache-2.0; see [LICENSE](LICENSE), [NOTICE](NOTICE), [third-party notices](THIRD_PARTY_NOTICES.md), and the [file-by-file rights clearance](docs/APACHE_RIGHTS_CLEARANCE_20261112.md). The frozen archive and wheel are excluded because their immutable nested evidence contains personal-data disclosures; this tree is not byte-identical to them. Ubuntu/aarch64 reproducible-build evidence is scoped to the exact tested worktree recorded in the [dated addendum](docs/UBUNTU_REPRODUCIBILITY_ADDENDUM_20261112.md): its Git HEAD was `8a9ace7ccac7f9cb491604350006273cf256c196`, with a separately recorded worktree identity. It produced two matching source archives and wheels and passed extracted-source replay; this is not a reproducibility claim for later commits. The addendum also records the separate Qiskit 2.6.2 distribution replay and its 0.2.2a1 provenance boundary. See the [gate matrix](RELEASE_GATE_MATRIX.md) for scope. Gate 1/native containment remains separately unresolved.
