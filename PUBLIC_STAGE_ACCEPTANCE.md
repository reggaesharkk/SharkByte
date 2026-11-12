# Public staging acceptance — SharkByte 0.2.1a2

This report covers the curated standalone-alpha source tree and evidence scoped to individual source identities. The frozen historical archive and wheel are not rewritten by these later acceptance records. Local raw receipts remain in the owner's acceptance archive, outside this public repository, because they contain workstation-specific paths.

## Initial Windows exact-tree acceptance (historical snapshot)

The initial staged package passed the isolated acceptance harness on Windows ARM64 / CPython 3.12.10 using a fresh virtual environment and pinned offline build wheelhouse with PEP 517 build isolation. The installed package was imported outside the checkout after clearing `PYTHONPATH` and `PYTHONHOME`.

- 13/13 acceptance checks passed; installed package source identity matched 14/14 files.
- The report recorded 30/30 tests in normal mode, `-O`, and `-OO`.
- Version, doctor, classical VM, quantum simulator, and bounded hybrid CLI checks passed.
- Both native backends exited 1 with the expected containment-unavailable refusal and no stdout. These are negative native-disabled checks, not tests of native functionality.
- That run's "not verified" statements below were true at the time and are retained as historical context.

### Initial run limitations, as recorded then

- GitHub Actions had not run at the time of that run.
- The run did not perform a fresh Ubuntu/aarch64 install of that exact staged tree.
- Native execution, containment, and cancellation were not verified.
- The archived-vector replay did not execute Qiskit.
- No physical quantum hardware was used.

## Dated evidence update — 2026-11-12

The following later receipts close only their stated checks and source identities. They do not rewrite the initial snapshot or establish acceptance for changes made after the corresponding tested source.

### Windows ARM64 Apache-closure acceptance

- Host: Windows ARM64, CPython 3.12.10.
- Fresh isolated PEP 517 install using the pinned offline build wheelhouse passed 13/13 harness checks; installed-source identity was 14/14.
- Regression suite: 37/37 tests in normal, `-O`, and `-OO` modes.
- Version, doctor, classical, quantum, bounded-hybrid, and both native-disabled refusal checks passed.
- The native checks confirm only that native execution is refused before execution.

### Ubuntu aarch64 source-archive reproducibility

- Host: Ubuntu/aarch64, CPython 3.14.4. The tested worktree identity was `worktree-sha256:f85ddd13830bd1c86c9818ebe2d08d986ac5dcbe92bb9b4d5040b685b4cf3821`; its recorded Git HEAD was `8a9ace7ccac7f9cb491604350006273cf256c196`.
- Two isolated PEP 517 builds produced identical source archives (84,413 bytes; SHA-256 `307b6313d562687017995fa45e53f6356be03133ed52501a882c86c1b7ddc181`) and wheels (57,879 bytes; SHA-256 `f3757d863c1743e9c45db7f5177dc85458f517767ee0ec5b0d2f672117f0cdab`).
- Fresh installation from the extracted source archive passed. Its 37 tests passed in normal, `-O`, and `-OO` modes. Classical, quantum, bounded-hybrid, and QASM smoke checks passed.
- The evidence manifest/readback covered 496 entries with zero mismatches. These byte-for-byte reproducibility results apply to the stated tested worktree, not automatically to later PR commits.
- `native_interpreter` and `direct_native` each exited 1 with `native backends are disabled: containment unavailable`; this is a negative refusal check only.

### Independent Qiskit distribution replay

- Ubuntu/aarch64 replay used Qiskit 2.6.2, OpenQASM3 parser 1.0.1, and `qiskit-qasm3-import` 0.6.0.
- 22 circuits and 320 basis-state probabilities matched the independent reference distributions. Maximum per-state absolute probability error: `4.440892098500626e-16`; maximum L1 distribution error: `5.273559366969494e-16`.
- The Qiskit comparison vectors are separately archived with SharkByte quantum provenance `0.2.2a1`; this does not claim whole-package identity with that version. No hardware was used.

### GitHub-hosted CI

GitHub Actions run [43173517464](https://github.com/reggaesharkk/SharkByte/actions/runs/43173517464) passed both GitHub-hosted Windows and Ubuntu jobs for PR #1 head `cb4db3d216fd53e90d466401907f8ab96722f2dc`. The later grammar and evidence-documentation commit `a816f564429dcc7f162a5b5f98162615e83feec1` was tested by [run 43188130663](https://github.com/reggaesharkk/SharkByte/actions/runs/43188130663); both `ubuntu-latest` and `windows-latest` jobs completed successfully. Hosted runner architectures are not claimed ARM64. These CI results are distinct from the Windows ARM64 and Ubuntu/aarch64 host receipts above.

## Scope and limitations

Supported scope is classical SharkVM execution, classical statevector quantum simulation, bounded hybrid orchestration, and OpenQASM generation. Native interpreter and direct-native execution remain disabled; Gate 1 containment/cancellation remains open. The VM is not a security sandbox. No physical quantum hardware execution is claimed. See [the release-gate matrix](RELEASE_GATE_MATRIX.md) for the status split by source and evidence scope.
