# Hadamard end-to-end certification: proof obligations

## Decision

**OPEN — Hadamard certification is not implemented or certified.** The existing exact bounded-support certificate remains restricted to X, Z, and CX signed basis permutations. Agreement among floating-point backends is empirical evidence and does not establish an end-to-end numerical bound.

## Reference semantics to define

For a finite binary64 input vector, each real and imaginary component is an exact dyadic rational. The ideal H gate on a selected qubit is the exact linear map

\[
  (a,b) \mapsto ((a+b)/\sqrt{2}, (a-b)/\sqrt{2}).
\]

The result is not normalized unless a separately specified normalization operation is requested. X, Z, and CX retain their exact signed-permutation semantics. The numerical implementation currently evaluates the constant `1 / sqrt(2)` in binary64 and rounds the additions and multiplications; this is a different computation from the exact map above.

## Exact algebraic representation route

For only X, Z, CX, and H, each component can be represented as `a + b√2`, with rational `a` and `b`, because the initial binary64 components are rational and H maps

\[
  \frac{(a_1+b_1\sqrt{2})\pm(a_2+b_2\sqrt{2})}{\sqrt{2}}
  = (b_1\pm b_2) + \frac{a_1\pm a_2}{2}\sqrt{2}.
\]

This would give an exact ideal simulator for that gate subset. It does not certify the existing binary64 engine. A certificate implementation would still need canonical rational encoding, bounded numerator/denominator growth, exact zero detection, and exact sign comparisons for deletion masses in `Q(√2)`. For a value `p + q√2`, ordering against zero can be decided using signs and integer comparisons after clearing denominators; no floating approximation may decide a deletion. Resource limits for coefficient growth and certificate replay would also need explicit fail-closed behavior.

For each deletion event, its squared mass is an algebraic number in `Q(√2)`. A conservative cumulative bound can charge an exact rational upper bound on its square root. The total deletion error is then at most the sum of these event bounds: each subsequent ideal gate is unitary and therefore preserves the prior difference norm, while the triangle inequality composes the new deletion error. This is the same hybrid argument used for sequential perturbations; no root-sum-square claim is justified without additional orthogonality proof.

## Existing binary64 engine route

To certify the current implementation rather than replace it with exact algebraic evolution, all of the following are required:

1. A rigorous enclosure for the exact coefficient `1/√2` and its difference from the stored binary64 coefficient, including the actual platform's IEEE-754 assumptions.
2. A conservative local error bound for every real addition/subtraction and coefficient multiplication used by H. It must include rounding of normal values, subnormal results, signed zero, underflow, and rejection of overflow or non-finite intermediates.
3. Separate ledgers for coefficient-evaluation error and complex component arithmetic error, plus a composition argument through every gate. Since H is unitary in the exact reference semantics, prior state error is not amplified by an ideal H; local rounding bounds can be added by the triangle inequality.
4. Exact or outward-rounded computation of event deletion mass from the actual stored binary64 coordinates. The cumulative ledger must add deletion error and gate error under one requested total budget. A fixed per-amplitude cutoff is insufficient.
5. An explicit normalization policy. The current certified subset does not renormalize. If output normalization is introduced, for a unit-norm ideal vector and pre-normalized error `ε < 1`, the conservative inequality `||y/||y|| - x|| <= 2ε/(1-ε)` follows from `||y|| >= 1-ε` and `| ||y||-1 | <= ε`. That extra term must be charged; it cannot be silently treated as zero.
6. A specified initial-state contract. If inputs are not required to be normalized, the certificate must bind and report their exact norm. If normalized inputs are required, validation itself must rigorously establish that property.

The local arithmetic bound could be computed by exact rational differences between each rounded binary64 operation and its exact dyadic operands, then enclosed against `1/√2` with rational intervals. This is auditable but potentially expensive. A simpler `γ_k` floating-point bound is only valid after proving its assumptions and adding a separate absolute underflow term for subnormals. Neither derivation has been implemented or independently checked in this branch.

## Required evidence before changing the decision

- A reviewed derivation and small exact-arithmetic reference implementation for `Q(√2)` comparisons and square-root upper bounds.
- An IEEE-754-specific local error ledger with documented subnormal/overflow behavior and hostile tests at cancellation, maximum finite, minimum normal, and subnormal boundaries.
- A replay verifier that recomputes the full gate, deletion, and normalization ledger without trusting generator-provided charges.
- Independent high-precision interval comparisons for cancellation-heavy and randomized circuits. They validate the implementation but do not replace the proof.
- Source-bound receipts and resource measurements for numerator growth, receipt size, generation time, and replay time.

Until these obligations pass, Hadamard input to the bounded certificate API must remain `UNSUPPORTED`; no tolerance change or empirical agreement may convert it into `PASS`.
