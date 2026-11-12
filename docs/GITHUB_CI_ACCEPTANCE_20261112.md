# GitHub Actions acceptance addendum — 2026-11-12

## Exact commit and run

- Repository: `reggaesharkk/SharkByte` (public)
- Pull request: [#1](https://github.com/reggaesharkk/SharkByte/pull/1), branch `release/apache-2.0-closure-20261112`
- Tested head commit: `3ddf25dc958e9102de239dde43f17f634e316414`
- Workflow run: [43171670647](https://github.com/reggaesharkk/SharkByte/actions/runs/43171670647)
- Workflow result: completed / success

## Jobs

| Job | Runner label | Python | Result |
|---|---|---:|---|
| `acceptance (windows-latest, 3.12)` | GitHub-hosted Windows | 3.12 | PASS |
| `acceptance (ubuntu-latest, 3.12)` | GitHub-hosted Ubuntu | 3.12 | PASS |

Both jobs completed checkout, Python setup, and the `Build isolated install and run regressions` step successfully. Hosted runner architecture is not represented as Windows ARM64 or Ubuntu aarch64; these CI results are separate from the previously recorded ARM64 host receipts.

The repository's default branch remained at `95f936aa32e10ee8ef726093889067086e4c4421` when checked. The PR remains open and unmerged. No release, tag, PyPI publication, or Zenodo deposit was created.

CI success establishes the workflow result for this commit, not Gate 1 native containment, ARM64 reproducible-build equivalence, physical quantum execution, or release readiness beyond the documented scope.

## Follow-up documentation commit

- Tested commit: `a816f564429dcc7f162a5b5f98162615e83feec1`
- Workflow run: [43188130663](https://github.com/reggaesharkk/SharkByte/actions/runs/43188130663)
- Result: both `acceptance (ubuntu-latest, 3.12)` and `acceptance (windows-latest, 3.12)` completed successfully, including the isolated install and regression step.

These are hosted CI results, not ARM64 host results. Native containment remains separate and open.

## Later CI run — 2026-11-12

GitHub Actions run [43173517464](https://github.com/reggaesharkk/SharkByte/actions/runs/43173517464) completed successfully for PR #1 predecessor head `cb4db3d216fd53e90d466401907f8ab96722f2dc`. The Windows and Ubuntu hosted jobs passed. These are GitHub-hosted runner results and do not establish ARM64 architecture.

## Latest documented follow-up CI — 2026-11-12

- Tested commit: `3caf0d61a3e73de0c324b6b5d4fa92f889ac8aa0`
- Workflow run: [43189130183](https://github.com/reggaesharkk/SharkByte/actions/runs/43189130183)
- Result: `acceptance (windows-latest, 3.12)` and `acceptance (ubuntu-latest, 3.12)` both completed successfully, including isolated installation and regression tests.

These hosted runners do not establish ARM64 host behavior. Native execution remains disabled and Gate 1 containment/cancellation remains open.
