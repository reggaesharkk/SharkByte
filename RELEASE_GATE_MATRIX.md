# Public alpha gate matrix - 0.2.1a2

| Gate | Status | Scope |
|---|---|---|
| Classical VM | PASS, scoped | Exact public tree installed and smoke-tested on Windows ARM64; 30 tests passed in normal, -O, and -OO. |
| Statevector simulator | PASS, scoped | Local CLI smoke and archived Qiskit comparison: 22 circuits / 320 probabilities. |
| Bounded hybrid | PASS, scoped | Four-iteration adaptive fixture through installed CLI. |
| OpenQASM output | PASS, scoped | 22 archived fixture outputs replay byte-for-byte; not universal conformance. |
| Exact public-tree install/regressions | PASS on Windows ARM64 | PEP 517 isolated install with pinned local wheelhouse; GitHub Actions pending. |
| Exact public-tree Ubuntu/aarch64 | NOT EXECUTED | No fresh acceptance of this exact curated tree. |
| Physical quantum hardware | NOT CLAIMED | No hardware executed. |
| Native interpreter / Direct AArch64 | DISABLED | Both refuse before native execution; negative guard tests passed. |
| Gate 1 containment/cancellation | CONDITIONAL / OPEN | Not resolved by this standalone alpha. |
| Security sandbox | NOT CLAIMED | VM limits are not isolation. |
| License | NOT SELECTED | Public visibility grants no license. |

Historical evidence applies only to its stated artifact, version, host, and scope. See PUBLIC_STAGE_ACCEPTANCE.md.
