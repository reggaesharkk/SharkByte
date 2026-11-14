# Public alpha gate matrix - 0.2.1a2

| Gate | Status | Scope |
|---|---|---|
| Classical VM | PASS, scoped | Exact public tree installed and smoke-tested on Windows ARM64; 30 tests passed in normal, -O, and -OO. |
| Statevector simulator | PASS, scoped | Local CLI smoke and archived Qiskit comparison: 22 circuits / 320 probabilities. |
| Bounded hybrid | PASS, scoped | Four-iteration adaptive fixture through installed CLI. |
| OpenQASM output | PASS, scoped | 22 archived fixture outputs replay byte-for-byte; not universal conformance. |
| Exact public-tree install/regressions | PASS on prior accepted snapshot | PEP 517 isolated Windows ARM64 install and scoped regressions are recorded in PUBLIC_STAGE_ACCEPTANCE.md; this local source revision needs its own CI result. |
| Exact public-tree Ubuntu/aarch64 install | NOT EXECUTED | No fresh full package-install acceptance of the exact current source tree on Ubuntu/aarch64. GitHub's ARM64 job checks the separate backend-agreement suite. |
| Physical quantum hardware | NOT CLAIMED | No hardware executed. |
| Native interpreter / Direct AArch64 | DISABLED | Both refuse before native execution; negative guard tests passed. They are not supported by this alpha. |
| Gate 1 containment/cancellation | OPEN for future native execution; excluded from this alpha | Containment and cancellation are not implemented or claimed. The gate must pass before native execution is enabled. |
| Security sandbox | NOT CLAIMED | VM limits are not isolation. |
| License | SELECTED: Apache-2.0 for current first-party tree | Earlier MIT-licensed revisions retain their original grant; see LICENSE_STATUS.md. |
| Hosted CI | PENDING for this revision | The published MIT snapshot passed hosted CI. The Apache license, fixed-point example, and grounded terminal answers need the current revision's run before this row can pass. |

Historical evidence applies only to its stated artifact, version, host, and scope. See PUBLIC_STAGE_ACCEPTANCE.md.
