# Contributor orientation

This file is a short orientation, not a copy of the full specification. The public repository is a separately curated SharkByte alpha. It is not the same checkout as other folders named `SharkByte` on the author's computers.

## Source of truth

- Read `SPEC.md` for supported behavior, limits, and record format.
- Read `GRAMMAR.md` for SharkByte source syntax.
- Read `COMPATIBILITY.md` and `CLAIM_BOUNDARIES.md` before changing backend or release claims.
- `LICENSE` is Apache-2.0 for the current first-party source distribution. Earlier MIT-licensed revisions remain available under the terms they were published with. Check each vendored component's notices and provenance before copying it elsewhere.
- Use `README.md` for public entry points. Do not rely on a local absolute path, another checkout, an old commit hash, or an old test count as current state.

## Important boundaries

- The installable CLI's native execution is disabled; its host-containment status is not a security sandbox claim.
- The included statevector and Frontier30 simulators run on the CPU. A 30-qubit register label does not mean a dense 2^30-state simulation.
- The optional local chat integration uses an external model runtime. A requested NPU backend or a `/doctor` setting does not by itself prove that inference ran on the NPU.
- Legacy backend agreement, native integration receipts, and private research systems are separate evidence tracks. Keep their source revisions and limits visible.

## Change discipline

- Preserve existing worktree changes. Review `git status` and the complete diff before staging anything.
- Keep private corpora, model weights, credentials, machine-specific paths, and unreviewed experiment receipts out of public commits.
- When changing a benchmark, regenerate its receipt from the exact committed source and keep exploratory resource caps separate from the public default.
- Update user-facing documentation when a command or evidence boundary changes. Do not claim a result that the corresponding receipt does not establish.
