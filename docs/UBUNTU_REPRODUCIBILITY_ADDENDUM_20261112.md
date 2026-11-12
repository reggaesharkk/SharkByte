# Ubuntu source-archive reproducibility addendum — 2026-11-12

This addendum records the authorized Ubuntu aarch64 host run `20261112T005205Z_54142`. Its candidate source was commit `8a9ace7ccac7f9cb491604350006273cf256c196`. This is historical test evidence for that exact source state; the current licensing closure branch adds license metadata and documentation, so current-tree checks are recorded separately in the branch review and CI.

## Host result

- `UBUNTU_REPRO_ACCEPTANCE=PASS`; `MANIFEST_READBACK=PASS`.
- 476 manifest entries were independently read back with zero mismatches.
- Two isolated source-archive builds were byte-identical: 73,613 bytes; SHA-256 `c6f12d85852e06198f053607d7b8f6a7b573dad94ab993271b7e24ff2e57a7c4`.
- Two isolated wheel builds were byte-identical: 52,748 bytes; SHA-256 `2eedac9921b62ae23cd8674e8b12a829aa0576e8e6a73af1c3e0e43dbafd8c9f`.
- The source archive contained 114 normalized members. PEP 517 build isolation remained enabled; build dependencies were resolved offline from the pinned wheelhouse.
- Fresh installation from the extracted source archive passed. The extracted-source test suite passed under normal, `-O`, and `-OO`; all three backend native guards refused execution as expected.
- Classical, quantum, QASM, hybrid, receipt/manifest and relevant smoke checks passed as recorded in the host receipt.

## Evidence identities

The host `complete.json` reported manifest SHA-256 `7bd58dfd9d02efb0fcbf74a996b77cbb98e8ff313563ca9bbbac362a493832f0` and test-summary SHA-256 `2311158bb43f524c1e8355ff7039d6cd1c705ce7de39f6daf4daf628124cb7b3`. Its own SHA-256 was independently rechecked as `c03c842414618c6d14dafeea33d58c34661f8abfd9b7010e13d8e34d71b03d81`.

These digests establish recorded artifact identity, not correctness by themselves. The Ubuntu result is host evidence; the Windows ARM64 install/regression receipt is separate. Cross-host byte-for-byte reproducible builds are not claimed. The reviewed branch must pass its own tests and GitHub Actions before this release closure is considered complete.

## Later Ubuntu worktree replay — 2026-11-12

A later authorized rerun is recorded under host evidence identifier `20261112T075914Z_59225`. This is additive evidence and does not replace or rewrite the earlier 476-entry run above.

- Host: Ubuntu/aarch64, CPython 3.14.4; evidence manifest/readback: 496 entries, zero mismatches.
- Candidate identity: `worktree-sha256:f85ddd13830bd1c86c9818ebe2d08d986ac5dcbe92bb9b4d5040b685b4cf3821`; recorded Git HEAD: `8a9ace7ccac7f9cb491604350006273cf256c196`. The worktree had modifications beyond that HEAD, so the receipt identifies the worktree and must not be described as a clean-commit replay.
- Two isolated PEP 517 builds produced identical source archives (84,413 bytes; SHA-256 `307b6313d562687017995fa45e53f6356be03133ed52501a882c86c1b7ddc181`) and wheels (57,879 bytes; SHA-256 `f3757d863c1743e9c45db7f5177dc85458f517767ee0ec5b0d2f672117f0cdab`).
- Fresh installation from extracted source passed; all 37 tests passed in normal, `-O`, and `-OO` modes. Classical VM, quantum simulation, bounded hybrid, QASM, and receipt/manifest checks passed. Both native backends refused execution with the expected containment-unavailable error; this verifies the guard only.
- The independently accepted Qiskit comparison is a separate evidence item: Qiskit 2.6.2 on Ubuntu/aarch64, 22 circuits / 320 probabilities, maximum per-state error `4.440892098500626e-16`, maximum L1 error `5.273559366969494e-16`. Its archived quantum vectors have 0.2.2a1 provenance; no whole-package identity or hardware execution is implied.

The later receipt does not establish reproducibility for the current public review branch. GitHub-hosted CI and host-built artifacts are distinct checks; CI for any later documentation commit must be read from that exact commit's Actions run.
