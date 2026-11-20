# H4 Gate 4a — historical-checkout replay across source revisions

## Decision and scope

This is a **candidate-v1 continuity experiment**, not acceptance of candidate-v2, cross-version mathematical equivalence, an installed certificate API, or authenticated execution. I establish a way to replay a historical v1 source/receipt using the exact previously accepted Git commit even if the current working source later changes.

The accepted research candidate at `1726b96a4fecf63dbec052bd0192e2741f1e653f` is the only registered version. The earlier Gate 3 verifier is intentionally dependent on the loaded seven-module H4 digest map: it returns `INVALID_RECORD` if the current engine drifts. Gate 4a offers a **different read-only route** that extracts the accepted historical code, checks its known SHA-256 manifest, and runs its own contained candidate verifier. This preserves a historical replay path without silently approving future source changes.

## Frozen trust boundary

1. The tool `tools.high_support.h4_historical_checkout` has a single hardcoded allowed commit; callers cannot select an arbitrary repository revision.
2. It requests that commit from the **local Git object store**, without network or checkout modifications. Full commit history must already be present.
3. It reads only the accepted `tools/`, `benchmarks/sb_quantum_benchmark/` source subtrees and the two accepted fixture files via `git archive`; extraction rejects path traversal, duplicates, links, unexpected member types, and over-limit archives.
4. It validates the SHA-256 of the candidate script, all seven recorded H4 engine modules, and original source/receipt fixtures **before executing** any historical Python code.
5. It invokes the accepted candidate-v1 CLI inside a disposable temporary tree. The historical CLI checks its own source/receipt pinning and independently replays the H4 numerical ledger under the existing 256-MiB worker containment and deadline policy. The parent checks that stdout's outcome agrees exactly with the exit status.
6. The historical temporary checkout and copied input files are removed. The repository, original receipts and Git objects are read-only.

A matching Git object and digest are **selection and integrity checks**, not an independent proof of what physical hardware executed a previous computation. Trust in the accepted historical source and Python interpreter remains an explicit assumption. The historical program should be executed only for a reviewed, trusted commit.

## Supported outcomes

| Result | Exit code | Meaning |
| --- | ---: | --- |
| `VERIFIED_PASS` | 0 | The pinned historical verifier independently replayed the receipt, and the computed error upper bound met the budget |
| `VERIFIED_BUDGET_EXCEEDED` | 1 | The historical mathematical receipt replayed, but its conservative upper bound exceeded the budget |
| `INVALID_RECORD` | 2 | Invalid, mismatched, altered or unreadable record; archive manifest mismatch; or incorrect CLI outcome |
| `UNSUPPORTED` | 3 | The pinned Git commit is unavailable, or the historical worker cannot run within its operational contract |

The 32-KiB source and 4-MiB receipt caps remain in force. Historical tar extraction is also bounded by an independent 3-MiB archive cap, 256-member limit, 2-MiB extracted-file limit and regular-file-only policy. The historical candidate retains at most eight qubits, 64 gates, no renormalization, no pruning, and restricted `x/z/cx/h` semantics.

## Reproduce

Use a **full-history** clone of the repository. The GitHub H4 workflow uses `actions/checkout` with `fetch-depth: 0`; an ordinary local clone normally already contains the accepted commit.

```sh
git cat-file -t 1726b96a4fecf63dbec052bd0192e2741f1e653f

python -B -m tools.high_support.h4_historical_checkout verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -O -m tools.high_support.h4_historical_checkout verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -OO -m tools.high_support.h4_historical_checkout verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json

python -B -m unittest tests.test_h4_historical_checkout -v
python -B -O -m unittest tests.test_h4_historical_checkout -v
python -B -OO -m unittest tests.test_h4_historical_checkout -v
```

The tests check accepted v1 replay using the historical checkout, source/receipt tampering, an altered snapshot module, simulated current-module import drift, unknown historical revisions, correct budget-exceeded status, and CLI exit/output agreement.

## Remaining obligations before any v2 or installed certificate

- No candidate-v2 implementation or receipt has been registered; therefore **equivalence between two different certificate versions is OPEN**. A hash allowlist alone must never be treated as a proof of cross-version numerical equivalence.
- Before any v2 registration, create separate exact source and receipt decoders and an independently audited translation or comparison theorem. Preserve original v1 bytes and full module hashes.
- Verify the historical-checkout execution model on native Windows ARM64 and Ubuntu WSL2 ARM64, including allowed Git histories, malformed archives, fail-closed operation and resource behavior.
- The parent Git archive operation is bounded by static accepted source size and fixed timeouts; it is **not a general-purpose sandbox for arbitrary Git trees**. Do not accept unknown source commits.
- Operating-system attestation and externally anchored authorship remain separate from mathematical replay.
- The installed/public signed-permutation certificate remains `x/z/cx` only; public Hadamard certification is still **UNSUPPORTED**.

**Acceptance gate:** hosted Windows/Ubuntu normal and optimized tests, native Ubuntu replay, and an independent hostile review of the extraction, version pinning, Python import isolation and failure codes. Do not merge until independently accepted.
