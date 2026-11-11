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

See PUBLIC_STAGE_ACCEPTANCE.md for exact-tree test scope. Local acceptance passed on Windows ARM64; GitHub Actions and fresh Linux/aarch64 acceptance of this precise public tree were pending at report time.

The frozen archive and wheel are excluded because their immutable nested evidence contains personal-data disclosures; this tree is not byte-identical to them. No license has been selected or authorized; public visibility is not a license grant. Gate 1/native containment remains separately unresolved.
