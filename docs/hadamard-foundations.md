# Hadamard mathematical foundations

I used the reconciled PR #25 audit at 24eeb64bd3 as a hypothesis list. The supplied HTML SHA-256 is 5bcf23e1fffce0dc646d2dd76eb637e2ad0f4bcf8bb0e95c8a6d37d08475bb3e.

## A1

I represent mass as (A + B sqrt(2))/D. For opposite-signed summands, I compare A squared with twice B squared and assign the sign according to which term dominates. With equal signs the result follows directly. For nonnegative ticks, squaring the desired covering inequality preserves order. I use exponential bracketing and binary search because coverage is monotone and eventually true for positive rational tick units. The search uses O(log(c+1)) comparisons for positive answer c. The costs of individual integer comparisons grow with operand bit length.

The audit's three-decrement claim fails. For mass sqrt(2) and unit 1/100, its starting estimate is 143 and the minimum is 119. I reproduced the Pell witness where p squared minus twice q squared equals one and binary64 subtraction gives zero. My tests retain both examples.

## A2

I treat each finite input coordinate as an exact dyadic. The exact real sum or difference is a multiple of 2^-1074, so a result in the subnormal range is representable. For a normal rounded sum I use a relative allowance u = 2^-53. I reject nonfinite sums and products. For the product I use relative allowance u in the normal range and absolute allowance 2^-1075 in the underflow range. The absolute allowance is a Fraction, including when its binary64 conversion would be zero.

I bracket the two coefficient errors by squaring rational endpoints around c sqrt(2). The historical coefficient falls below the ideal by 0.798 to 0.799 units of u, and its adjacent upper coefficient is above by 0.615 to 0.616 units. The midpoint is below the ideal, as follows by squaring twice the midpoint's square against one. The historical coefficient remains the only coefficient used by the experiment. The product of the worst relative factors is bounded by (1+u)^2 (1+0.799u), strictly below 1+3u.

I apply the scalar inequality to the four real coordinates of each complex pair. Minkowski and the unitarity of ideal H give 3u times the input norm plus 2 sqrt(M) times 2^-1075 for M active pairs. Exact replay uses rational nearest-even rounding of the real operations and independently bounds the squared distance to the ideal output using an integer square-root interval. Its arithmetic cost includes large integer roots and is intended for small research cases.

This result is conditional on separately rounded binary64 operations in nearest-even mode with gradual underflow and the CPython complex operation sequence. The environment checks are probes. They do not attest to compiler flags, dynamic rounding state, or other runtimes. Nonfinite intermediates, alternative arithmetic orders, flush-to-zero, and unsupported runtimes are outside the proof. Multiplication by the real coefficient may involve exact zero cross terms in CPython complex multiplication. They affect signed-zero bits and do not affect the mathematical enclosure.

## Composition and identity

For ideal unitary U and current computed input y, I split the next error into U applied to the previous difference, the local arithmetic defect at y, and any deletion defect. Unitarity preserves the first norm. The triangle inequality adds the local enclosure and the deletion charge. A local bound uses the computed input norm at that step, or an upper bound from the initial norm plus the accumulated error. I cannot substitute a constant unit norm after deletion or rounding. For a nonzero computed output and a unit ideal state, exact normalization adds at most the previous error by the reverse triangle inequality. Rounded normalization would need a separate charge. I have not implemented a cumulative certificate.

I distinguish an IEEE-754 representation digest, which includes the sign of zero, from mathematical identity, which identifies both zeros as rational zero. The transcript records raw bits. The independent rounding replay checks mathematical coordinates and intentionally does not attest to output zero signs. No new public digest schema is introduced. The historical reproduction tests retain the interference and q20 coefficient residuals. Hadamard remains UNSUPPORTED in the certified-support interface.

I run the focused suite with python -B, python -B -O, and python -B -OO followed by -m unittest tests.test_hadamard_foundations. I can generate a sample transcript with python -B tools/high_support/hadamard_transcript.py and replay it by passing the saved JSON path to the same command.
