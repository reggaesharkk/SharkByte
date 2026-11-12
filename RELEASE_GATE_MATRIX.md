# Public standalone alpha gate matrix — evidence update 2026-11-12

This matrix separates implementation scope from the identity, host, and date of each verification. Historical reports remain intact; later evidence applies only to the exact source/artifact described.

| Gate | Status | Evidence and scope |
|---|---|---|
| Classical VM | PASS, scoped | Fresh installed CLI checks and regression suites passed on Windows ARM64 and Ubuntu/aarch64 host candidates. See `PUBLIC_STAGE_ACCEPTANCE.md`; no security-sandbox claim. |
| Classical statevector simulator | PASS, scoped | 22 circuit distributions were compared with an independent Qiskit 2.6.2 replay: 320 basis probabilities; maximum per-state error `4.440892098500626e-16`; maximum L1 error `5.273559366969494e-16`. Provenance is separately scoped to the archived 0.2.2a1 quantum vectors. |
| Bounded hybrid orchestration | PASS, scoped | Adaptive four-iteration fixture and broader hybrid acceptance completed; observed zero-state counts `[906, 1250, 1675, 1950]` for the cited fixture. The outer orchestration is bounded; no general-purpose quantum-classical loop claim. |
| OpenQASM generation and replay | PASS, scoped | Qiskit imported and simulated 22 emitted circuits; bit ordering and measurement conventions are covered by the archived fixtures. This is not universal OpenQASM conformance or hardware acceptance. |
| Windows ARM64 installed acceptance | PASS, host-reported | Apache-closure host receipt: 13/13 acceptance checks, installed-source identity 14/14, and 37/37 tests in normal, `-O`, and `-OO`. Native checks were expected refusal tests only. |
| Ubuntu/aarch64 source-archive reproducibility | PASS for stated worktree | Two isolated builds of recorded worktree identity `worktree-sha256:f85ddd13830bd1c86c9818ebe2d08d986ac5dcbe92bb9b4d5040b685b4cf3821` (recorded Git HEAD `8a9ace7ccac7f9cb491604350006273cf256c196`) produced matching sdist and wheel hashes; extracted-source install and 37 tests in each Python optimization mode passed; manifest readback 496/496. This does not identify later PR commits. |
| GitHub-hosted CI | PASS on predecessor PR head; current docs commit pending | Run [43173517464](https://github.com/reggaesharkk/SharkByte/actions/runs/43173517464) passed Ubuntu and Windows hosted jobs for `cb4db3d216fd53e90d466401907f8ab96722f2dc`. Runner architecture is not claimed ARM64. CI for this documentation update must be checked on its exact commit. |
| Apache-2.0 rights and notices | PASS, owner-attested scope | The owner selected and authorized Apache-2.0 for rights-established curated project files. Per-file provenance is documented in `docs/APACHE_RIGHTS_CLEARANCE_20261112.md`; this is not an independent legal opinion. |
| Native interpreter / Direct AArch64 | DISABLED | Both backends refuse with `native backends are disabled: containment unavailable`. These checks verify refusal only; native execution is not accepted. |
| Gate 1 containment and cancellation | CONDITIONAL / OPEN | Complete native process containment and end-to-end cancellation are separate unresolved security obligations. |
| Physical quantum hardware | NOT CLAIMED | All reported quantum results are classical simulation or external simulation. |
| GitHub Release/tag, PyPI, Zenodo | NOT AUTHORIZED / NOT EXECUTED | No publication or release tag is part of this evidence update. |

See [the staged acceptance report](PUBLIC_STAGE_ACCEPTANCE.md), [Apache closure history](docs/APACHE_RELEASE_CLOSURE_20261112.md), and [Qiskit replay provenance](docs/PUBLIC_QISKIT_REPLAY_ADDENDUM_20261112.md). Neither matching hashes nor CI success alone proves computational correctness or closes Gate 1.
