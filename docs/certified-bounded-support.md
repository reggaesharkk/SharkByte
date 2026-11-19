# End-to-end numerical certificate for signed permutations

## Reference semantics

This certificate deliberately supports only x, z, and cx. The state index uses the repository convention that qubit q0 is the least significant bit. x(q) toggles that bit. z(q) multiplies a basis amplitude by minus one when that bit is one. cx(c,t) toggles target bit t when control bit c is one.

The supplied initial state is a finite, nonempty mapping from basis integers in `[0, 2^n)` to Python complex binary64 values. Each real and imaginary component is interpreted as the exact dyadic rational encoded by its IEEE-754 bits. Zero entries are omitted. The input need not have unit norm and is not normalized. This defines a precise input reference. Conversion from decimal text or a previously normalized state into binary64 is outside the certificate.

Output is the unnormalized vector of length `2^n` after applying the listed gates and permitted coordinate deletions; an omitted dictionary key denotes an exact zero coordinate. The API does not renormalize. A normalization request returns UNSUPPORTED. Angle-bearing gates have no semantics in this certified subset. h, rx, ry, rz, and cp return UNSUPPORTED, including cancellation-heavy sequences containing them.

## Error derivation

Let the exact input be x and each supported gate be Uj. Each Uj is a signed basis permutation and therefore unitary. Its matrix coefficients are exactly 0, +1, or -1. The implementation uses dictionary key permutations and component sign changes. On finite binary64 values, those operations are exact. Therefore coefficient-evaluation error, complex gate-arithmetic error, and accumulated gate-rounding error are all zero for this gate subset and environment.

At deletion event j, let dj be the vector whose coordinates are exactly the removed amplitudes and zero elsewhere. Its squared norm is the exact rational sum of each real component squared plus each imaginary component squared: `m_j^2 = ||d_j||_2^2 = sum_k (Re(d_j[k])^2 + Im(d_j[k])^2)`. The verifier reconstructs these values from the exact binary64 input and canonical float.hex witnesses.

The ledger tick is `t = B / 2^32`, where B is the requested positive rational budget. The event charge is the smallest integer `k_j` satisfying `m_j <= k_j t`, equivalently `k_j = ceil(sqrt(m_j^2 / t^2))`. Integer square root on exact rational integers computes this ceiling without a floating-point square root. The verifier checks the exact minimum charge. The remaining tick count is reduced by `k_j` after each event, so `sum(k_j) <= 2^32` and `sum(m_j) <= sum(k_j t) <= B`.

Writing the compacted recurrence as yj+1 = Uj yj - dj, unitarity gives ||xj+1-yj+1|| <= ||xj-yj|| + ||dj||. Induction therefore bounds the final unnormalized vector error by the sum of event norms, which the ledger bounds by B. The verifier also evolves an independent exact rational reference without deletions and checks the final squared difference directly against the certified bound.

Normalization is disabled, so its error contribution is exactly zero. If normalization is later added, its cost must be separately derived and charged. This certificate does not establish behavior for mixing gates, rounded trigonometric coefficients, decimal-input conversion, other numeric formats, or a broader gate engine.

The optional `protected` list names fixed basis indices at every compaction point. It does not identify a physical branch and does not move when x or cx permutes coordinates. A low-amplitude branch can move away from a protected index and be deleted; the deletion remains covered by the L2 ledger. The `fixed-protection-moves` adversarial case records this behavior. Callers that need branch preservation must update the coordinate set as gates are applied or decline compaction for that branch.

## High-precision reference and uncertainty

For certified cases, the reference state and squared error are represented as exact Fraction values and have zero representation uncertainty. For display, the square root of the exact error is enclosed by integer arithmetic in a dyadic interval with denominator 2^1200. The interval width is either zero or exactly 2^-1200. NumPy, Qiskit, and Cirq comparisons use complete vectors and were exact for the tested signed-permutation workloads. The exact-rational result is the proof basis, not a floating comparison tolerance.

For the prior 48 schedules and five cancellation, subnormal, rotation, and interference controls, the checker also computes full-vector references using `mpmath.iv` at 100 decimal digits. Each binary64 angle and initial component is enclosed as its exact dyadic rational; outward-rounded interval endpoints are serialized exactly, with a SHA-256 digest, and vector error upper bounds include the endpoint uncertainty. NumPy, Qiskit, Cirq, and unpruned sparse outputs are compared separately. These high-precision comparisons are experimental evidence and do not extend the certificate. The circuits include mixing and/or angle gates, so the certification API returns `UNSUPPORTED` for all 48 schedules and all interference controls.

For those unsupported general-gate runs, unpruned sparse-to-interval error measures the baseline floating execution discrepancy, while compacted-to-interval error measures total observed error. The record also compares each compacted full vector with NumPy, Qiskit, and Cirq, and records the compacted-to-unpruned vector difference. That pairwise difference is diagnostic only: prior deletions can change later gate inputs, so it is not an independent proof of the deletion term. Only the restricted signed-permutation path has a certified decomposition in which all gate-rounding terms are zero.

## Reproduction and decisions

Run from the repository root with CPython using IEEE binary64 and the pinned dependencies. The recorded local Windows ARM64 run used CPython 3.12.10; the WSL2 comparison run used CPython 3.14.4. GitHub CI uses Windows x64 and Ubuntu with CPython 3.12:

    python -m pip install -r requirements-high-support.txt
    python -m unittest discover -s tests -p test_certified_support.py -v
    python tools/high_support/check_certified_support.py > certified-support-evidence.json

The record includes source and implementation hashes, all 48 prior unsupported outcomes and numerical comparisons, seeded certified workloads, exact reference hashes, interval-reference digests and uncertainty bounds, external simulator versions, event charges, and adversarial cases. The committed Linux and native Windows ARM64 records are linked in [REPRODUCIBILITY.md](../REPRODUCIBILITY.md).

| Acceptance item | Decision |
|---|---|
| Exact gate, input, output and normalization semantics | PASS for this documented subset |
| Coefficient and gate arithmetic bound | PASS with zero error for x, z, cx on finite binary64 inputs |
| Repeated deletion composition | PASS by exact integer/rational ledger verification |
| Prior 48 schedules | PASS as 48 explicit UNSUPPORTED results with fresh high-precision full-vector comparisons |
| Subnormal and repeated-deletion signed-permutation cases | PASS by exact rational replay |
| Cancellation, interference, and tiny-angle controls | PASS as high-precision numerical comparisons; certification explicitly UNSUPPORTED |
| Mixing, angles, decimal conversion error and renormalization | OPEN and returned as UNSUPPORTED |
| Expansion to general quantum gates | OPEN; requires a separate validated coefficient and arithmetic-error analysis |

This is an exact numerical guarantee for a narrow subset. It does not certify the default simulator or enable compaction by default.
