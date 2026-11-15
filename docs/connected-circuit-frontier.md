# Connected-circuit verification and compiler hardening

Status: experimental evidence on the isolated `codex/connected-circuit-frontier`
branch, based on source revision `db140939c4ed96447f3d614653c128e5a41df2f3`.
This report is separate from earlier verification tracks and is not a release
claim.

## What is new

The earlier evidence already covered 120 Qiskit/Cirq circuits through six
qubits and a 16,777,216-active-state run whose interaction graph split into
eight disconnected components. Those results were not repeated here.

This experiment adds 24 new circuits with connected two-qubit interaction
graphs: 20 fixed-seed randomized circuits (two each at 2, 3, 4, 5, 6, 8, 10,
12, 14, and 16 qubits), plus four adversarial cases. Each random prefix has
random local rotations and two connected interaction layers; the complete
source also applies the exact inverse. Qiskit and Cirq independently build and
evolve the source-derived ordered gates. Their full statevectors are compared
for the entangling prefix and the inverse circuit. Source text and SHA-256
identity match across both reference runs.

The four adversarial cases cover exact gate/phase cancellation and ±4π angle
boundaries, a connected low-support GHZ state with non-Clifford/local gates,
the accepted 256-gate source limit, and a connected graph that is still
separable. The 256-gate case also checks that a 257th gate is refused.

## Results

| Check | Result |
| --- | --- |
| Qiskit 2.6.2, Windows ARM64 | 24/24 PASS |
| Cirq 1.7.0, Windows ARM64 | 24/24 PASS |
| Direct Qiskit/Cirq prefix and inverse comparison | 24/24 PASS |
| Largest global-phase-aligned amplitude difference, Qiskit vs Cirq | 4.78e-15 |
| Largest probability difference, Qiskit vs Cirq | 6.22e-15 |
| Largest Qiskit vs sparse-simulator amplitude difference | 5.49e-16 |
| Largest Qiskit vs sparse-simulator probability difference | 6.67e-16 |
| Eight-qubit GHZ all-bipartition analytic check | PASS, Schmidt probabilities 0.5 and 0.5 |
| Connected GHZ closed-form checks at 20, 24, 30, and 40 qubits | 4/4 PASS on Windows ARM64 and Ubuntu WSL2 |

The reference runs used isolated Windows ARM64 environments with CPython
3.12.10, NumPy 2.5.4, Qiskit 2.6.2, and Cirq 1.7.0 on a Qualcomm Oryon
Snapdragon X X126100 CPU. Qiskit and Cirq were run separately. Full source,
gate-order metadata, reference vectors, and hashes are in the evidence
directory. The comparison script additionally computes reduced-density-matrix
purity by matrix products and checks it against the separate SVD Schmidt
witnesses in the two run receipts.

The first Qiskit run completed all simulations but stopped while serializing
the receipt: a NumPy `int64` Schmidt rank is not a JSON-native integer. The
failure log is preserved in the evidence bundle. The rank is now converted to a
built-in integer, and the final Qiskit and Cirq receipts were regenerated into
fresh paths; the incomplete first state archive remains in the local
exploration artifacts and is not presented as a completed receipt. Public log
files use normalized LF line endings and replace machine-local paths with
placeholders; the receipts retain their full result fields and integrity
digests.

## Connected graph is not an entanglement proof

Every circuit graph in the corpus is connected, but the six-qubit negative
control is a product state: each CNOT is immediately canceled by a second
identical CNOT, each controlled-phase angle is zero, and the remaining gates
are local. Its complete 64-amplitude vector matches the independently written
tensor-product formula. The Qiskit and Cirq receipts report purity 1.0 on all
four tested cuts. This explicitly rejects the inference that graph
connectivity alone implies entanglement.

The random-circuit and eight-qubit cases are classified only across the cuts
listed in their receipts. For the GHZ family, the two branches differ on every
nonempty proper subset and its complement, giving Schmidt rank two with
probabilities (0.5, 0.5) across every bipartition. The 20–40-qubit cases use
that exact closed-form GHZ oracle and a sparse simulator; they do not use a
dense Qiskit or Cirq statevector. They establish this specific connected GHZ
family, not arbitrary 40-qubit circuits.

## Performance profile and rejected change

The Windows ARM64 benchmark uses the same seeded connected prefixes at 12,
14, and 16 qubits, one warmup and seven timed repeats. It reports the median
and median absolute deviation. `tracemalloc` peak Python-heap measurements
were taken in separate runs, so memory instrumentation does not affect the
timing samples. These values are Python-tracked heap, not total process RSS or
system peak memory.

| Width | Peak support | Baseline median | MAD | Traced Python heap peak |
| ---: | ---: | ---: | ---: | ---: |
| 12 | 4,096 | 0.04724 s | 0.00026 s | 1.19 MiB |
| 14 | 16,384 | 0.22911 s | 0.00216 s | 4.79 MiB |
| 16 | 65,536 | 1.17412 s | 0.00720 s | 20.07 MiB |

The 16-qubit cProfile run placed nearly all measured execution time in the
Python sparse `evolve` loop, especially per-gate state transforms and
dictionary lookups. An in-place `rz`/`z`/`cp` update experiment was measured
on the same cases and rejected: it was 12.13%, 7.27%, and 4.13% slower at 12,
14, and 16 qubits, while saving at most 0.49% of traced heap. That code was
reverted. No performance gain is claimed; optimizing the Python sparse gate
kernel remains open.

## Compiler counterexample and fix

The source-size limit alone did not protect the recursive compiler. Before the
fix, a 3,008-byte source with 1,500 nested parentheses and a 3,006-byte source
with 1,500 chained additions each escaped as an unhandled `RecursionError`.
The addition-chain failure reproduced in both the v0.4 and v0.5 parser paths.

The compiler now enforces the documented 65,536-byte UTF-8 source limit even
when called through its direct API, rejects nesting deeper than 128, and
limits each additive or multiplicative expression chain to 128 operators.
Those conditions raise deterministic `SharkError` diagnostics. Invalid
surrogate text is also reported as a controlled language error. Regression
tests cover both parser paths and accepted/rejected boundaries.

Windows ARM64 and Ubuntu WSL2 each passed all 49 unit tests. The isolated
package acceptance also passed all checks on Windows ARM64 with CPython
3.12.10 and Ubuntu WSL2 aarch64 with CPython 3.14.4. In both environments,
the copied package passed normal, `-O`, and `-OO` test runs (49 tests each),
all CLI smoke checks, and explicit native-backend refusal checks. Native
execution remains disabled.

The new `connected-statevector-reference` CI job runs the 24-case Qiskit/Cirq
comparison independently on GitHub's Ubuntu and Windows Python 3.12 runners and
uploads the two receipts, statevectors, and comparison report. This is a
repeatable CI check for the new corpus; it does not rerun the prior 120-case
suite or the 16,777,216-state benchmark. The recorded local ARM64 measurements
above remain distinct from the hosted CI environments. The job also verifies
the checked-in byte manifest from a clean GitHub checkout.

## Reproduction

Run the dense reference comparisons in separate environments with the pinned
versions above:

```powershell
python -B tools/run_connected_quantum_validation.py --backend qiskit --output qiskit.json --support-cap 65536 --memory-budget-mib 64 --timeout-seconds 60
python -B tools/run_connected_quantum_validation.py --backend cirq --output cirq.json --support-cap 65536 --memory-budget-mib 64 --timeout-seconds 60
python -B tools/compare_connected_quantum_receipts.py qiskit.json cirq.json --output comparison.json
```

Run the analytical sparse family without Qiskit or Cirq:

```sh
python3 -B tools/run_connected_sparse_analytic_validation.py --output analytic.json
```

Run the new tests with `python -B -m unittest tests.test_connected_quantum_corpus
tests.test_compiler_hardening -v`, or run the repository's full unit and
isolated-install acceptance commands. Verify the packaged receipt, state-vector,
source, and report hashes with:

```sh
python3 -B tools/verify_connected_circuit_evidence.py
```

SHA-256 here is an unkeyed integrity mechanism. It detects byte changes; it
does not establish authorship or independent correctness by itself.
