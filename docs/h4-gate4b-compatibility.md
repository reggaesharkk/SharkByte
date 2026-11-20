# H4 Gate 4b compatibility contract

I register only candidate-v1 from commit 1726b96a4fecf63dbec052bd0192e2741f1e653f. I compare two explicitly selected requests and their certificates. The same selector on both sides establishes the reference baseline. I reject an unknown selector. Synthetic differences in tests exercise comparison policy and create no accepted version.

## Candidate-v1 semantics

- Source and receipt are ASCII JSON with sorted object keys, compact separators and exactly one terminating LF. Duplicate names and noncanonical spellings are rejected. Source SHA-256 binds the original bytes. The internal H4 source digest binds its JSON string encoding.
- A basis-index row contains two exactly 16-character lowercase binary64 hex words. I decode sign, exponent and fraction to exact dyadics, including subnormals and both signs of zero. Omitted coordinates start at positive zero. Nonfinite words and overflow are rejected. Input index order is strictly increasing.
- Wire zero is the least significant basis-index bit. X toggles the target, Z flips its sign when the target bit is set, and CX toggles its target only when its control bit is set. H applies real and imaginary butterflies independently, with ordered sums and differences rounded before multiplication. I preserve gate order as certificate semantics.
- Ideal H uses 1/sqrt(2). Its software coefficient is word 3fe6a09e667f3bcc, exactly 1592262918131443/2^51. Software rounding is nearest-even with gradual underflow. Adding two negative zeros yields negative zero. Other exact cancellations yield positive zero. Subtraction toggles the second operand's sign first, and multiplication by the positive coefficient preserves the sign when it rounds to zero.
- The candidate accepts finite, unnormalized states, one to eight qubits, up to 64 gates and no deletion schedule. The exact initial squared norm is charged as part of the reconstructed ledger data. Each H allowance is 3u times the outward norm of the actual input plus the outward bound on sqrt(M) times 2^-1074. Here u=2^-53 and M counts active pairs. Outward roots are on the 2^-1100 grid. Signed permutations have zero local arithmetic charge. Every deletion charge is zero.
- I independently check the bound at every ideal prefix. I represent the ideal coordinates as dyadics times the common factor 2^(-h/2), where h counts Hadamards. For odd h, a sign-aware squared comparison handles sqrt(2) exactly. The cumulative upper bound is the sum of gate charges. A reduced nonnegative rational is the requested L2 budget. A verified upper bound over budget leaves actual accuracy undecided.
- The version, candidate script SHA-256 and H4 source hash map identify expected behavior. I compare all independently reconstructed ledger fields, including ordered output words, charges, norm bounds, budgets, outcomes and both final state digests. An implementation identifier alone establishes none of these facts.

## Separately reported results

| Category | Evidence I require |
| --- | --- |
| Syntax | Both original encodings pass their specified parsers. I separately report exact source byte equality. |
| A. Archival | The original Git object and pinned manifest validate, and independent rational reconstruction matches each full receipt. The Gate 4a launcher separately exercises execution from the pinned historical tree. |
| B. Mathematical | Exactly equal interpreted dyadic inputs, equal ordered gate semantics, equal normalization policy and equal exact ideal prefix states. I refuse to infer general equivalence from coincidentally equal final outputs. |
| C. Bit level | Mathematical trace compatibility, equal arithmetic contracts and equal initial and per-step words. I report observed word equality separately. |
| D. Certificate | Compatible mathematics and bits, equal reconstructed charges, equal rational budgets and equal independently verified decisions. Neither a weaker bound nor a format translation is accepted in this gate. |
| E. Execution authenticity | Always unauthenticated. Git and content hashes establish correspondence to known bytes, without identifying an operator or proving where execution occurred. |

I use exit 0 for compatible comparisons, 1 for valid records whose compatibility is unproved, 2 for invalid records and 3 for unsupported comparisons. A compatibility result is distinct from the two per-receipt accuracy outcomes. If both verified bounds exceed budget, compatibility can pass while both within-budget flags are false.

The pinned launcher uses bounded Git archive extraction and the historical worker limits of 256 MiB with a 25-second arithmetic worker deadline. The new comparator executes no archived code. It reads at most 32 KiB per source and 4 MiB per receipt, independently checks the pinned tree, and uses a cooperative 20-second replay deadline per side and bounded rational trace dimensions. The comparator does not add a separate OS memory supervisor. I keep that engineering obligation open for untrusted-service exposure. Missing historical Git objects yield unsupported. Damaged pinned contents, malformed records and reconstruction disagreement fail closed.

## Reproduction and evidence

From the repository root with full Git history:

    python -B -OO -m tools.high_support.h4_historical_checkout verify evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
    python -B -m tools.high_support.h4_compatibility sharkbyte-xz-cx-h-candidate-v1 evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json sharkbyte-xz-cx-h-candidate-v1 evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
    python -B -m unittest tests.test_h4_compatibility

I repeat the tests under -O and -OO. The pinned historical producer regenerates the original receipt byte for byte in a temporary tree, generates a mixed repeated-H fixture with cancellation, signed zero and minimum subnormal inputs, and generates a valid zero-budget refusal. The new checker independently reconstructs all three. The stored comparison is [the v1 reference result](../evidence/h4-compatibility/v1-baseline.json).

The archived candidate source and receipt hashes are 9bda8fe9794ea6af6ab431ee1c6b81ccf8ad792ef1f11f5668ff7568bb761d59 and 2d5d9f4a767cca1fe933a05f7b729efb1e72db4dbe6c0ac48e96bbd981909c33. The candidate implementation hash is 6f2d5a700f553e9a3c0fab0eb4e64ff1c20fd7872523f0acfd24ab6439189a69. The full dependency manifest is in the Gate 4a launcher. This comparator's LF-normalized source hash is 50dcab082ab2c6db7de76a71883b59b83f1fa4a66be4832d02ddd771c25b7a8a.

## Candidate-v2 registration remains open

I require a reviewed, frozen parser and verifier for the prospective version; a complete pinned dependency manifest; documented normalization, gate, coefficient, rounding, budget, and resource semantics; independent replay of the full trace and adverse boundary fixtures on each supported environment; and an explicit compatibility rule for each category above. If bits or charges differ, I require a separate proof before accepting any translation or weaker compatibility relation. Authentic execution needs evidence external to the receipt. No candidate-v2 is registered, and the public signed-permutation API and its unsupported Hadamard boundary remain separate.
