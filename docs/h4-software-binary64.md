# H4 Gate 1: deterministic software binary64

I start from merged H3 at d9d4bb4104dd7849ac4f16940bea832053fbb714. I reviewed PR #28 separately. Its archival gate checks H3 mathematical agreement and intentionally accepts differences in the sign of zero. I use the original ARM64 receipts as the native comparison baseline.

## Execution contract

I interpret each finite binary64 word as an integer multiple of 2^-1074. I compute X and CX by permuting coordinates and Z by toggling both component sign bits. For H, I compute each real and imaginary coordinate separately. I round each sum or difference first and then multiply by the historical 1592262918131443/2^51 coefficient and round again. I retain gradual underflow and reject overflow at either operation. There are no native floating-point operations in the simulated gate arithmetic.

My producer rounds with integer quotient, remainder and parity. The verifier uses exact rational arithmetic and searches the ordered finite bit encodings for the adjacent results. It chooses by exact midpoint comparison and ties to the even encoding. It rejects at or above the overflow midpoint beyond the maximum finite value. For exact sums of zero I use +0 except for -0 plus -0. Subtraction changes the second operand's sign before applying this rule. Multiplication by the positive coefficient keeps the operand's sign, including when the rounded magnitude is zero. The dense experiment includes signed zeros at every coordinate. Deletion replaces both words with +0.

## Ledger and proof

I bind the external source text, including the initial words and ordered gates and deletions, to the versioned ledger. Replay independently reconstructs each word and every charge, including the sign of zero. I retain separate final hashes of the dense bit representation and of the exact mathematical state. The latter omits zero coordinates and identifies both signs of zero. The versioned format is experimental and separate from the H3 archives.

I apply the H3 composition theorem at each gate. For H, I use 3u times the outward bound on the actual input norm plus the outward bound on sqrt(M) times 2^-1074. Here M counts pairs with at least one mathematically nonzero input. For deletion I charge an outward square root of the exact dyadic mass removed. The verifier recomputes both charges with its own outward root implementation and checks the full cumulative inequality against the exact ideal algebraic state after every gate. I leave normalization disabled.

## Limits and reproduction

I retain the H3 width limit of 8 qubits, 64 gates, the existing source and ledger read limits, and 256 MiB per worker. Each arithmetic worker has a 20-second internal deadline and a 25-second external deadline. Windows uses Job committed memory and Linux uses RLIMIT_AS address space. Timings and peak resident memory in the wrapper are observations. The ledger verifies arithmetic and source binding. I do not treat wrapper telemetry as authenticated.

    python -B -m tools.high_support.h4_run evidence/h3/circuit.json h4-new.json
    python -B -OO -m tools.high_support.h4_run evidence/h3/circuit.json h4-new.json --replay
    python -B -m unittest tests.test_h4_software

I also exercise normal Python, -O and -OO. Producer work grows with register size even at low support. Replay may perform up to 63 rational comparisons per scalar rounding, with two rounds per component. The ledger stores all component words at every gate. These are research tradeoffs and therefore I make no throughput or scalability claim from the archive fixture. The public certified-support interface continues to reject Hadamard.

## Observed cost on the nine-gate fixture

| Host | H3 generation / replay | H4 generation / replay | H4 peak resident generation / replay |
| --- | ---: | ---: | ---: |
| Windows ARM64 | 2.92 / 12.41 ms | 4.52 / 23.09 ms | 26.5 / 30.3 MiB |
| Ubuntu WSL2 ARM64 | 16.23 / 18.04 ms | 18.40 / 33.55 ms | 25.3 / 25.4 MiB |

I measured one fixture on each host and compared with the archived H3 observations. The ledger grew from 28,008 to 31,730 bytes. Across all prefixes, the mathematical states and charges agreed with both H3 archives. Among the coordinates H3 stored, I found four zero-sign differences on Windows and none on WSL2. H3 omitted entirely zero complex coordinates, so the native comparison does not assign bits to those missing entries. The H4 ledgers agree across both hosts, including their dense bit digests. I recorded the source hashes, worker limits and times in the two H4 receipts.
