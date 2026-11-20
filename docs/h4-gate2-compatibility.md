# H4 Gate 2 — public certificate compatibility research

I am separating **compatibility of mathematical results** from **compatibility of certification formats and execution policies**. The first does not imply the second.

## What I tested

The versioned public `benchmarks/sb_quantum_benchmark/certified_support.py` interface retains the signed-basis-permutation contract `binary64-input/signed-permutation/canonical-unnormalized-v1` (plus the separate moving-origin policy). It certifies only finite binary64 `x`, `z`, and `cx` operations within its budget, input, and environment restrictions.

The standalone H4 research engine uses `sharkbyte-h4-software-binary64-v1`. It includes `h` but has different input and output representations, research budget grammar, gate-count and register limits, software-defined rounding semantics, dense bit-recording, resource supervision, and independently replayable rational error charges.

The regression `tests/test_h4_gate2_compatibility.py` checks three boundaries:

1. For one exact `x/z/cx` overlap fixture **without amplitude deletion**, public v1 and H4 produce the same rational amplitude at every basis coordinate. This is a narrow overlap check, not evidence of interchangeable certificates, generalized performance, or support-pruning equivalence.
2. A Hadamard circuit independently replays with a `PASS` research ledger while the same circuit remains `UNSUPPORTED` in public v1. Passing H4 evidence cannot be substituted for a public signed-permutation certificate.
3. Public normalization remains unsupported, public budgets must lie strictly between zero and one, and H4's separate integer-budget source syntax does not change the public contract.

The tests run under normal CPython, `-O`, and `-OO` on both hosted Windows and Ubuntu CI through `.github/workflows/h4-software.yml`.

## Matrix of current semantics

| Property | Public v1 signed-permutation certificate | H4 experimental research ledger |
| --- | --- | --- |
| Operations | `x/z/cx` only | `x/z/cx/h` within research limits |
| Inputs | CPython finite binary64 complex components | Canonical dense binary64 word representation from a bounded JSON source |
| Calculation | Exact signed coordinate permutations, with optional deletion | Explicit binary64 nearest-even software step with rational replay |
| Output | Sparse dictionary and signed-permutation certificate | Dense per-coordinate bits and an independent mathematical error ledger |
| Budget | Absolute rational `0 < budget < 1` for opt-in compaction | Separate bounded rational H4 source budget, outcome `PASS/FAIL` |
| Normalization | Unsupported for certification | Disabled |
| Signed zero | Mathematical amplitudes do not certify exact zero-sign bits | Reconstructs recorded software arithmetic output bits |
| Receipt integrity | Source-bound v1 certification fields | H4 ledger plus optional versioned strict envelope validation |
| Execution provenance | Not authenticated by hashing | Also not authenticated |
| Supported public Hadamard API | **UNSUPPORTED** | **Not integrated** |

## What remains open before public H certification

**Gate 2 is not closed by these tests.** A future public H-capable certificate would require an explicitly versioned new API/format, not a silent change to the signed-permutation v1 semantics.

Before proposing any such interface, I need:

- A precise transformation from bounded client inputs into the H4 source contract. Decimal parsing, initial-state normalization, basis ordering, signed zeros, and input digest semantics must be explicit and tested.
- A strict separation of *verified FAIL* from *invalid certificate*, and independently checked generation/replay outputs plus each intermediate arithmetic/deletion charge.
- Resource and denial-of-service controls across source parsing, ledger generation, strict verification, and serialization. The current research cap (up to eight qubits and 64 gates) is not a public throughput promise.
- Exhaustive boundary testing of subnormals, near-overflow, cancellations, repeated `h`, mixed `x/z/cx/h` gate sequences, and adversarial deleted coordinates within scope.
- A compatibility plan that replays archived v1, H3 and H4 evidence without altering raw bytes or recorded source hashes.
- Explicit conclusions about the existing mathematical assumptions, exact coefficient, software arithmetic contract and external provenance. Content integrity does not authenticate its author or runtime.

I will not certify mixing-gate compaction or a generalized normalized result without independent theorems and replay covering those semantics.

## Reproduce

```sh
python -B -m unittest tests.test_h4_gate2_compatibility -v
python -B -O -m unittest tests.test_h4_gate2_compatibility -v
python -B -OO -m unittest tests.test_h4_gate2_compatibility -v
```

No public API, H3/H4 arithmetic module, historical receipt, or license needs modification for this gate. I am preserving the distinction between an exact overlap witness, a reusable certificate contract, and an authenticated execution record.
