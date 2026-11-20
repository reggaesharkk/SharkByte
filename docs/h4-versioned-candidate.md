# H4 Gate 2 experimental certificate candidate

I provide this candidate as an opt-in command in the source checkout. I keep the installed signed-permutation v1 API and its receipt format separate. The candidate supports finite, unnormalized X/Z/CX/H circuits up to eight qubits and 64 gates. Its source schema has no deletion schedule or normalization option.

## Contract and replay

The request has exactly five fields: contract, qubits, initial, gates and budget. The contract identifier is sharkbyte-xz-cx-h-candidate-v1. I use ASCII JSON with sorted object keys, compact separators, no duplicate names, and exactly one terminal LF. The gate list preserves circuit order, with each gate encoded as [operation, wires]. Initial rows have strictly increasing unique basis indices and two lowercase, sixteen-digit IEEE-754 words. Missing indices start at positive zero. Explicit rows can retain either zero sign. I use little-endian qubit indexing, with qubit zero represented by the least significant basis-index bit.

The encode_source helper accepts pairs of finite built-in floats and a nonnegative Fraction without coercion. It encodes each component with big-endian struct packing, including negative zero and subnormals. The budget is its reduced rational spelling. Exact source bytes, including the version, initial words, gate order and budget, are bound by SHA-256. The receipt also binds the candidate implementation and the existing H4 module map. The new receipt is a canonical envelope over the independently replayable H4 ledger, with no host telemetry.

I execute with the existing H4 software integer engine and replay with the separate rational engine. Replay reconstructs every output word, active pair count, outward norm and arithmetic charge, cumulative bound and decision. The replay also checks every prefix against the algebraic ideal state. The translated H4 ledger has an empty deletion schedule at every gate, so every deletion charge is zero and is independently checked. I retain the historical H coefficient and existing nearest-even and gradual-underflow contract. The bound is an upper bound on L2 error against the unnormalized ideal computation.

| Result | Exit status | Meaning |
| --- | ---: | --- |
| VERIFIED_PASS | 0 | The verified upper bound is within budget |
| VERIFIED_BUDGET_EXCEEDED | 1 | The verified upper bound exceeds budget. Actual error may still be within budget |
| INVALID_RECORD | 2 | Malformed input or receipt, failed replay, or output publication refusal |
| UNSUPPORTED | 3 | Unsupported contract, operation, size domain, arithmetic overflow during generation, or worker environment |

I cap source and receipt reads at 32 KiB and 4 MiB. The Windows and Linux supervisors impose the inherited 256 MiB commit or address-space cap, respectively, with a 25-second worker deadline and a 60-second outer deadline. The numerical functions retain their 20-second arithmetic deadline. Generation and verification run in separate bounded workers, with atomic no-overwrite publication after both agree. The Python helpers are useful for conversion, testing and independent replay. The CLI is the contained entry point.

## Reproduce

From the checkout root:

    python -B -m tools.high_support.h4_candidate generate evidence/h4-candidate/source.json candidate-new.json
    python -B -OO -m tools.high_support.h4_candidate verify evidence/h4-candidate/source.json candidate-new.json
    python -B -m unittest tests.test_h4_candidate

The fixture includes mixed gates, an explicit negative-zero input and a minimum subnormal component. The archived candidate receipt supports bit-level and mathematical replay. I also run the focused tests under -O and -OO and exercise historical H3/H4 receipts separately.

## Review obligations

I keep this candidate experimental. I still need independent review of the canonical encoding, budget and module pinning policy, transition rules for future implementations, and compatibility before any installed API exposure. The new modules are version-bound at replay, so future changes need an explicit compatibility policy or replay at the recorded revision. Hashes bind content and provide no execution authentication. The tested boundary excludes normalization, pruning, general sparse mixing and wider circuits. I make no claim that all supported-size circuits fit each host's runtime or that this stage proves a general floating-point result.

## Frozen historical v1 replay

The separate [H4 candidate archive verification policy](h4-candidate-archival-policy.md) records the exact accepted v1 implementation SHA and H4 module map. Its read-only, bounded command verifies the original source and receipt without importing the potentially changed candidate script:

```sh
python -B -m tools.high_support.h4_candidate_archive verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
```

This archival tool checks the fixed version identity and independently recomputes all numerical fields. It does not authorize reinterpreting an unknown implementation as v1, and it fails closed if the underlying H4 replay dependencies drift. The installed public certificate remains unchanged.
