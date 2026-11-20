# H4 Gate 3 — frozen candidate-v1 archive replay

I preserve the independently accepted source-checkout H4 candidate-v1 as a **historical certificate contract**, not as an installed public API. The archive verifier is a separate read-only, resource-bounded command. It does not modify the candidate generator, the signed-permutation public API, historical H3/H4 records, or the accepted candidate fixture.

## Pinned version and provenance boundary

| Property | Fixed archived value |
| --- | --- |
| Accepted implementation commit | `1726b96a4fecf63dbec052bd0192e2741f1e653f` |
| Candidate source contract | `sharkbyte-xz-cx-h-candidate-v1` |
| Candidate implementation SHA-256 | `6f2d5a700f553e9a3c0fab0eb4e64ff1c20fd7872523f0acfd24ab6439189a69` |
| Internal H4 ledger schema | `sharkbyte-h4-software-binary64-v1` |
| Fixture source SHA-256 | `9bda8fe9794ea6af6ab431ee1c6b81ccf8ad792ef1f11f5668ff7568bb761d59` |
| Pinned module-hash map | `tools/high_support/h4_candidate_archive.py`, `ARCHIVED_H4_MODULES` |
| Reference fixture | `evidence/h4-candidate/source.json` and `receipt.json` |

These SHA-256 values are **content identifiers**, not signatures or evidence that a named machine executed a workload. An externally trusted commit or hash pin is needed to establish the expected source. The pin alone does not establish computational correctness.

## New read-only verification command

From the checkout root:

```sh
python -B -m tools.high_support.h4_candidate_archive verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -O -m tools.high_support.h4_candidate_archive verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -OO -m tools.high_support.h4_candidate_archive verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -m unittest tests.test_h4_candidate_archive -v
```

The archival verifier freezes the canonical v1 request decoder independently of the mutable `h4_candidate.py` script, including key order, exact terminal LF, sorted initial indices, reduced rational budget, explicit binary64 words, fixed gate ordering and enforced absence of deletion schedules. It accepts only the recorded candidate implementation digest and the **complete** recorded internal H4 module-hash dictionary.

It then independently calls the existing rational H4 replay engine to check **every recorded bit, gate, prefix charge, mathematical enclosure, budget outcome and final digest**. No hash match can bypass that mathematical replay. Receipt and source reads retain their 4 MiB and 32 KiB limits. Verification runs in the existing bounded worker with the 256 MiB platform containment policy and a worker deadline. The archive command never creates or overwrites a receipt.

| Outcome | Exit | Interpretation |
| --- | ---: | --- |
| `VERIFIED_PASS` | 0 | Valid archived certificate with verified upper bound inside budget |
| `VERIFIED_BUDGET_EXCEEDED` | 1 | Valid archived certificate with upper bound outside budget; actual error may still be smaller |
| `INVALID_RECORD` | 2 | Unknown or mixed implementation hash, malformed source/record, drifted dependency, or failed replay |
| `UNSUPPORTED` | 3 | Unsupported source contract or worker environment |

## Scope of forward compatibility

**Candidate-script-only changes:** the archival verifier does not import the live candidate script. A future refactoring that changes its self-hash will not automatically make the original v1 receipt unreadable through this separate verifier, provided the accepted request semantics and pinned H4 replay dependencies remain available.

**H4 mathematical engine changes:** the original receipt pins the exact hashes of seven internal modules. The current H4 replay engine additionally checks its loaded module identities. If these modules change, this archive verifier deliberately **fails closed**; it does not silently admit a new implementation under old evidence. At that point use a checked-out copy of accepted commit `1726b96a` or introduce a separately reviewed, kernel-equivalent historical replay implementation with adversarial regression evidence.

**Future candidate contracts:** semantic or envelope changes must use a new contract name (for example, `sharkbyte-xz-cx-h-candidate-v2`) and an independently audited parser and replay path. Adding a candidate SHA to an allowlist is not proof of mathematical equivalence. Each archived version must retain exact source bytes, a pinned implementation identity, the full ledger module map, and independently replayed result semantics. Never map unknown hashes to a current implementation without explicit review.

The test suite checks a simulated future candidate-script hash drift, budget-exceeded exit code 1, hostile modifications to candidate and module pins, tampered numerical charges, altered source binding, canonical source rules, and non-writing archive behavior.

## What this does not authorize

This is a **replay-compatibility milestone**, not general public Hadamard certification. The accepted finite and unnormalized `x/z/cx/h` candidate remains opt-in, no-pruning, at most eight qubits and 64 gates. The public signed-permutation certificate still supports only its documented subset, and neither execution provenance nor universally bounded runtime is claimed. 
