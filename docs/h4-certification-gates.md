# H4 — archival replay and certification boundaries

I treat a passing H3 research ledger as a scoped mathematical result, not as permission to expand the public certified-support interface. I preserve the H3 source revision, historical coefficient, archive content, and the experimental label.

## Gate 0: archived-receipt compatibility

The first H4 gate verifies the original Windows ARM64 and Ubuntu WSL2 ARM64 H3 receipts from `evidence/h3/` without regenerating them or changing the six H3 arithmetic modules. The regression test `tests/test_h4_archived_h3.py` independently replays each recorded ledger on the CI host and checks:

- Original circuit SHA-256 and recorded implementation hashes.
- Each archive's original PASS decision and all intermediate arithmetic/deletion charges.
- Exact mathematical agreement between the two hosts' input/output coordinate values, per-gate charges, and final state identity.
- Rejection of changed source, coefficient, gate-event count, pairing count, charges, reordered events, or nonzero amplitude bits.
- Explicit separation of IEEE-754 representation bits from mathematical identity: replay can accept a flipped zero sign, but must reject a changed nonzero coordinate.

I regard this as an archival compatibility and verifier tamper test. It does **not** authenticate the author of an archive, prove bit-exact signed-zero execution, attest to the native arithmetic environment, or independently re-run the archived Windows/WSL2 simulations.

## Gate 1: native arithmetic-environment contract — OPEN

I need a versioned statement binding the runtime, CPython complex operation sequence, actual coefficient bits, rounding mode, gradual underflow, signed-zero handling, nonfinite refusal, and any compiler/processor assumptions. Representative probes are useful evidence, not a universal attestation. A conforming runtime must be tested with hostile arithmetic cases, and unsupported behavior must fail closed.

## Gate 2: certificate compatibility — OPEN

Before I expose an H-capable public certificate, I must prove compatibility with the existing signed-permutation v1 receipt contract or introduce a separate opt-in version. I must independently recompute every intermediate state, norm bound, arithmetic charge, deletion charge, and final decision. Historical receipts must remain readable. I must define budget, resource, and normalization semantics explicitly; normalization remains disabled here.

I will not silently change the historical `1/math.sqrt(2)` coefficient or canonicalize archived raw-bit hashes. A future bit-exact zero-sign contract must be versioned and proved separately.

## Gate 3: public integration — OPEN

Only after Gates 1 and 2 pass do I consider exposing a restricted `X/Z/CX/H` certified mode. The current public `certified_support` API continues to return `UNSUPPORTED` for H. H3 still has bounded research scope: at most eight qubits, 64 gates, 256 coordinates, resource-limited workers, and conditional binary64 assumptions.

The central discipline remains unchanged: **I want every error allowance independently computable, and every certification claim limited to the environments and operations for which its hypotheses are established.**

## Reproduction

Run on both supported CI operating systems:

```sh
python -B -m unittest tests.test_hadamard_foundations tests.test_h3 tests.test_h4_archived_h3
python -B -O -m unittest tests.test_hadamard_foundations tests.test_h3 tests.test_h4_archived_h3
python -B -OO -m unittest tests.test_hadamard_foundations tests.test_h3 tests.test_h4_archived_h3
```

The archived receipts remain unchanged. This gate does not start billable infrastructure or require optional quantum-reference libraries.
