# H3 cumulative Hadamard research ledger

I bound error against the original circuit acting on the exact dyadic values of its finite binary64 inputs. Wires are little endian. I do not normalize. I interpret omitted coordinates and either sign of zero as mathematical zero. The input source preserves the supplied component bits. The post-gate records preserve the observed component bits on nonzero complex entries, and replay checks mathematical equality. It does not attest to the sign of an output zero.

## Composition

Let y be the computed input, x the ideal input, U the next ideal gate, z the rounded output before deletion, and w the retained output. I expand w-Ux as (w-z)+(z-Uy)+U(y-x). The triangle inequality and unitarity give E_next <= E_previous + G + D. The initial difference is zero because the same exact dyadics initialize both paths.

For X, Z and CX, the arithmetic charge is zero under the finite binary64 signed-permutation semantics. For H, I use the historical coefficient and the A2 arithmetic order. An active pair has at least one mathematically nonzero complex coordinate before the gate. An inactive pair contributes zero. For M active pairs I charge 3u R(||y||^2) + R(M) 2^-1074, with u=2^-53. I use R(t)=ceil(2^1100 sqrt(t))/2^1100. The dyadic grid and integer root comparison round outward. I compute the squared input norm exactly at every gate. The squared initial norm in the ledger specifies the norm exactly as its nonnegative square root.

Each deletion is a source-specified coordinate projection after its gate. I sum the squares of the real and imaginary components actually removed and charge R of that mass. A requested coordinate that is already zero adds zero. The deleted values are stored binary64 dyadics, even when the ideal reference involves sqrt(2). I retain the exact underflow allowance and sum all charges as rationals. I make no independence assumption. An exceeded budget produces FAIL in both generation and replay.

## Replay and resource scope

I hash the JSON source string with the shared canonical JSON encoding. Replay takes the original source separately and checks its digest, the module digests, the coefficient, operation semantics, all charge fields, every retained state, and the final mathematical digest. The source contains the initial bits, ordered gates and ordered deletion schedule. Module hashes use UTF-8 text with universal newline decoding. These hashes bind content and are not signatures.

The producer evaluates sparse native complex operations. The verifier maintains separate dense arrays for exact rational rounding and ideal evolution. In the ideal array each H performs unscaled sum and difference. After h Hadamards the common factor is 2^(-h/2). For each prefix I calculate squared error from the actual and initial squared norms and their dot product with the ideal array. For odd h the comparison reduces to a signed rational comparison against a rational multiple of sqrt(2), decided by squaring only after accounting for signs. This independently checks the full ideal error at every prefix, including any coherent buildup. An inequality failure rejects replay with a FAIL diagnostic.

I limit the experiment to 8 qubits, 256 populated coordinates, 64 gates, bounded JSON reads and bounded input budget numerator and denominator lengths. Each ideal numerator is a sum of at most 2^64 input terms before accounting for permutation and cancellation. Binary64 coordinates have a common 2^-1074 grid, so squared masses have a common 2^-2148 grid. Roots and cumulative charges use fixed grids. Integer bit lengths therefore depend on these input caps, and do not grow without bound. Dense replay scans O(gates * 2^qubits) coordinates, with rational arithmetic and square-root costs in addition. Explicit post-states make the ledger scale as O(gates * support).

I run generation and replay in separate supervised workers, each limited to 256 MiB and 25 seconds, with an internal arithmetic deadline and a 60-second outer generation deadline. Windows applies Job committed memory and Linux applies RLIMIT_AS address space. Neither is the peak resident measurement. The receipts record measured peak resident memory, times and bytes. Publication is atomic. I scope native generation to the historical CPython binary64 operations, nearest-even with gradual underflow, with nonfinite intermediates refused. Environment probes are not an attestation of compiler or floating-point settings. Software replay checks the resulting mathematical coordinates independently.

## Reproduce

    python -B -m tools.high_support.h3_run evidence/h3/circuit.json new-receipt.json
    python -B -OO -m tools.high_support.h3_run evidence/h3/circuit.json new-receipt.json --replay
    python -B -m unittest tests.test_h3 tests.test_hadamard_foundations

I also run the tests with -O and -OO. The fixture includes interference, entanglement and multiple deletion requests. The suite checks exact prefixes for 20 seeded mixed circuits and a 64-H coherent drift case, including subnormals, cancellation, nonfinite refusal, altered coefficients, reordered gates, forged states and insufficient charges.

## Acceptance

I establish the conditional composition theorem and provide an experimental generator, independent verifier and hostile prefix tests. The two platform receipts reproduce one contained experimental case each. Public end-to-end certification remains OPEN. In particular I have not established environment attestation, general scalability or public certificate schema compatibility. Hadamard remains UNSUPPORTED in the existing certified-support API.
