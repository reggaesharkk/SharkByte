# Apache licensing and public alpha closure — 2026-11-12

## Decision scope

This branch prepares the curated SharkByte standalone alpha source tree for an Apache-2.0 licensed public alpha. It is not a GitHub Release, version tag, PyPI publication, or Zenodo deposit. Apache-2.0 is applied to this tree only. The excluded frozen source archive and wheel, earlier frozen releases, and unrelated repositories are outside this licensing action.

## Rights and notices

The owner selected Apache-2.0 and expressly authorized licensing the project material for which the owner holds rights. The owner confirmed that the `prince upadhyay` commit identity is theirs and that they hold rights to those changes. Git history attributes the 55 files in the prior source/evidence rights inventory to the public repository owner identity `reggaesharkk`; the project owner confirms that author identity and grants Apache-2.0 for these curated project materials. All 55 files were independently rehashed against that inventory with exact byte-size agreement. Per-file details and basis are in [the rights clearance](APACHE_RIGHTS_CLEARANCE_20261112.md).

This is a provenance record based on owner attestation, not an independent legal opinion. The package does not bundle Qiskit or other third-party runtime libraries. External build/test tools are enumerated in [third-party notices](../THIRD_PARTY_NOTICES.md). The root `NOTICE` and `LICENSE` are included in the source distribution and wheel metadata.

## Reproducibility evidence

The authorized Ubuntu aarch64 acceptance evidence for source commit `8a9ace7ccac7f9cb491604350006273cf256c196` recorded a 476/476 manifest readback, zero mismatches, and two byte-identical isolated sdist builds and two byte-identical isolated wheel builds. The artifact hashes are recorded in [the Ubuntu addendum](UBUNTU_REPRODUCIBILITY_ADDENDUM_20261112.md). A separate Windows ARM64 receipt recorded fresh PEP 517 installation, 37 tests each under normal, `-O`, and `-OO`, installed-source identity 14/14, and the native-backend negative guard tests.

The Ubuntu duplicate-build receipt is for the pre-closure commit above; it is not a reproducibility claim for the licensing closure tree. On the closure working tree, a fresh Windows ARM64 / CPython 3.12.10 PEP 517 installation using the pinned offline build wheelhouse passed 13/13 acceptance checks: installed import outside checkout, source identity 14/14, 37 tests each in normal, `-O`, and `-OO`, version/doctor/classical/quantum/hybrid smoke checks, and both expected native-disabled refusals. The machine-readable host receipt is `WINDOWS_APACHE_BRANCH_ACCEPTANCE.json` in the user's local acceptance staging directory and is intentionally not copied into the public source tree. The short temporary path was necessary for the Windows isolated build; a longer temporary path failed with a setuptools bytecode-cache path error and that failed run is preserved outside this tree.

The current closure-tree Ubuntu installation/reproducibility run has not been performed. The earlier Ubuntu reproducibility gate remains PASS for its recorded pre-closure artifact only. The exact closure commit must pass the repository's GitHub-hosted Ubuntu and Windows CI before branch integration; those hosted results are a separate gate. Do not interpret the Ubuntu duplicate builds as cross-platform byte-reproducibility proof.

## Capability and security boundaries

- Supported scope: classical SharkVM, classical statevector quantum simulation, bounded hybrid orchestration, and OpenQASM generation.
- Native interpreter and direct-native execution remain disabled. Their refusal tests are negative checks, not native functionality tests.
- Gate 1 process containment/cancellation remains open and independent of this alpha licensing work.
- No physical quantum hardware run is claimed. The VM is not a security sandbox or general-purpose production compiler.

## Release gate snapshot

| Gate | Status at closure preparation |
|---|---|
| Owner rights authorization for inventoried curated project files | PASS — owner-attested; 55/55 identities verified |
| Apache-2.0 repository and package metadata/notices | PASS — included in packaging metadata and installed successfully in the current Windows ARM64 isolated PEP 517 acceptance |
| Ubuntu isolated reproducibility evidence | PASS for accepted pre-closure commit only; NOT RE-RUN on this closure tree |
| Windows ARM64 isolated install and regression evidence | PASS on current closure working tree — 13/13 checks; 37 tests in each optimization mode; native refusal is a negative guard test only |
| Current branch regression/disclosure checks | PASS locally: 37 tests in each Python mode; public-content scan covered 105 files with no findings; all 106 manifest entries independently matched byte sizes and SHA-256; `git diff --check` clean |
| GitHub Actions on reviewed branch commit | PENDING — must complete on the exact branch commit |
| Gate 1 native containment/cancellation | OPEN / CONDITIONAL; native stays disabled |
| GitHub Release, tag, PyPI, Zenodo | NOT AUTHORIZED in this mission |

## GitHub Actions result

After this closure state was prepared, GitHub Actions run [43171670647](https://github.com/reggaesharkk/SharkByte/actions/runs/43171670647) completed successfully for PR #1 head commit `3ddf25dc958e9102de239dde43f17f634e316414`. The `acceptance (windows-latest, 3.12)` and `acceptance (ubuntu-latest, 3.12)` jobs both completed with conclusion `success`; their isolated install/regression steps also passed. This is hosted-runner evidence for that exact commit, not ARM64 host evidence. See the dated [CI addendum](GITHUB_CI_ACCEPTANCE_20261112.md).

The branch is pushed for review; no release tag or package publication was made. Gate 1 remains open, and Ubuntu ARM64 reproducibility for the exact Apache closure tree remains unverified.

## Later evidence update — 2026-11-12

The preceding release-gate snapshot is retained as a record of what was known when that closure report was written. Subsequent evidence is scoped as follows:

- Ubuntu/aarch64 reproducible sdist and wheel builds, extracted-source installation, and 37 tests in normal, `-O`, and `-OO` passed for the separately identified worktree `worktree-sha256:f85ddd13830bd1c86c9818ebe2d08d986ac5dcbe92bb9b4d5040b685b4cf3821` whose recorded Git HEAD was `8a9ace7ccac7f9cb491604350006273cf256c196`. This does not establish reproducibility for every later PR commit. Exact artifact hashes and the 496-entry readback are recorded in [the staged acceptance report](../PUBLIC_STAGE_ACCEPTANCE.md).
- Direct Ubuntu/aarch64 Qiskit 2.6.2 replay compared 22 circuits / 320 probabilities against the independent archived vectors; maximum per-state error was `4.440892098500626e-16`, and maximum L1 error was `5.273559366969494e-16`. The separate quantum provenance is described in [the Qiskit addendum](PUBLIC_QISKIT_REPLAY_ADDENDUM_20261112.md); it does not imply whole-package identity with v0.2.2a1 or hardware execution.
- GitHub Actions run [43173517464](https://github.com/reggaesharkk/SharkByte/actions/runs/43173517464) passed on predecessor PR head `cb4db3d216fd53e90d466401907f8ab96722f2dc` for GitHub-hosted Ubuntu and Windows. CI for any later documentation commit must be checked separately.

These updates do not close Gate 1. Native execution remains disabled, and no GitHub Release, tag, PyPI publication, or Zenodo deposit is authorized by this report.
