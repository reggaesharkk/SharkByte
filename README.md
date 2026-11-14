# SharkByte standalone alpha 0.2.1a2

A separately curated, source-only public snapshot of a bounded experimental language toolchain. It includes an installable Python CLI, SharkVM, classical statevector simulator, bounded hybrid orchestration, examples, tests, and a scoped independent Qiskit reference fixture set.

**Start with `main` for current SharkByte source and benchmarks.** Its first-party source uses the standard [MIT License](LICENSE), SPDX identifier `MIT`. See [License and branch history](LICENSE_STATUS.md) for the archived Apache candidate.

**Cite SharkByte standalone alpha 0.2.1a2** using the Zenodo version DOI. The archive preserves source commit `f5c537a76fe2f1cab12288fa29f6820cf453eb40`. [DOI 10.5281/zenodo.24213559](https://doi.org/10.5281/zenodo.24213559)

## Supported functionality
- Classical SharkVM execution with a 50,000,000-instruction limit.
- Classical CPU statevector simulation for the documented quantum subset.
- Bounded hybrid execution with measurement feedback and limited adaptive updates.
- OpenQASM 3 output for the documented subset.
- SHA-256 receipt integrity checking; hashes do not authenticate a record.

The installed CLI supports SharkVM and refuses native execution. Quantum circuits run in a classical simulator. SharkVM is not a security sandbox.

## Reproduce the public benchmarks

- [Backend agreement](benchmarks/backend_agreement/README.md) runs SharkVM, Direct AArch64, and the native interpreter from a source checkout on Linux ARM64 with Python, Clang, and LLD. On the [verified source revision](https://github.com/reggaesharkk/SharkByte/commit/0beed08fc99235d8de1f594448dfa7fc80a46c08), nine programs passed on each backend (27/27), and all three produced the expected diagnostic for their configured 50,000,000-instruction or tick budget. Use trusted local programs. Host isolation remains unverified.
- [Frontier30](benchmarks/sb_quantum_benchmark/) runs bounded sparse simulations of `.sb` circuits on a classical CPU, including 30-qubit cases. The [same CI run](https://github.com/reggaesharkk/SharkByte/actions/runs/43512576013) passed the Windows and Ubuntu jobs and published the benchmark receipts.

The [Reggae Shark Universe](https://github.com/reggaesharkk/Reggae-shark-universe-) indexes SharkByte alongside the other public projects.

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

See [PUBLIC_STAGE_ACCEPTANCE.md](PUBLIC_STAGE_ACCEPTANCE.md) for the original public snapshot's Windows ARM64 acceptance record.

The frozen archive and wheel are excluded because their immutable nested evidence contains personal-data disclosures; this tree is not byte-identical to them. This project is licensed under the MIT License; see LICENSE for details. Public visibility is not a license grant beyond the terms of LICENSE. Gate 1/native containment remains separately unresolved.
