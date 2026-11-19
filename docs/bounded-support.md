# Bounded sparse support experiment

The opt-in runner starts in basis state zero and advances the existing sparse kernel one gate at a time. Use a decimal L2 budget, a positive gate interval, and optional protected basis indices. For example:

```
python -m benchmarks.sb_quantum_benchmark.bounded_support examples/high_support/roundtrip_17q.sbq --budget 1e-10 --interval 214 --support-cap 131072 --memory-mib 256 --seconds 180 > record.json
python -m benchmarks.sb_quantum_benchmark.verify_bounded examples/high_support/roundtrip_17q.sbq record.json
```

## Audit and bound

Sparse H and rotation kernels sum amplitudes and retain nonzero floating results. Dense NumPy allocates the full vector regardless of support. Adaptive sparse evolution delegates to the sparse kernel, and on dense steps counts represented nonzeros for density decisions. Residuals can keep that count high. This experiment operates only on sparse states. Candidate sorting, exact rational arithmetic and the deletion log consume additional memory beyond the sparse kernel estimate.

At each scheduled boundary, sort eligible coordinates by squared magnitude and basis index. Delete the longest affordable prefix while retaining at least one coordinate. Protected indices are excluded. For decimal budget B, one ledger tick is B/2^32. For deleted vector d, charge the smallest integer k with ||d||? <= (k ticks)?, using exact rational arithmetic on the stored binary components. If the charge exceeds the remaining allowance the prefix is shortened. Repeated events draw from the same ledger.

In ideal unitary arithmetic the next deviation is U times the preceding deviation minus the deleted vector. Unitarity and the triangle inequality give a final L2 deviation at most the sum of the event norms, bounded by B. For the executed floating-point circuit, each gate also introduces a local rounding error. The certificate accounts only for deletion, and fresh full-vector comparisons measure the combined error on the tested circuits.

The returned vector is unnormalized. If a caller scales a nonzero vector v to unit norm, this adds |1 - ||v|| | to the triangle bound; that cost has not been charged. The runner returns no samples or normalized probabilities. A global L2 allowance can spend the entire amplitude of a physically meaningful small branch. Use `--protect INDEX` to forbid deletion at that fixed coordinate at every boundary. The optional `--protect-branch INITIAL_INDEX` follows an initial coordinate through x, z, and cx gates; multiple origins may be supplied by repeating the option. Moving-branch mode rejects h and all mixing or angle gates. Fixed-index and moving-branch modes cannot be combined. Both are opt-in, and neither changes default simulation behavior.

Moving-branch identity is exact only for these signed basis permutations: x changes the mapped bit, z changes only sign, and cx conditionally changes the target bit. It tracks the initial coordinate amplitude, not a physical branch through a superposition. The certificate records the origin and final coordinate mapping; `verify` independently recomputes the mappings and checks that no deletion event removes a currently protected coordinate. See [the certified subset specification](certified-bounded-support.md).

## Replay and measurement

The verifier re-executes the original sparse gates, checks each hex-encoded deleted amplitude, recomputes its squared mass, and checks the ledger and surviving support. Replay requires matching sparse floating-point results. It shares the gate kernel but does not call the compactor. The dense, Qiskit and Cirq controls compare every complex amplitude without phase alignment. Their acceptance check reports the ledger charge separately from a 1e-13 numerical comparison allowance.

Run `python tools/high_support/check_bounded.py` with the dependencies in `requirements-high-support.txt`. The output records gates, implementation hashes, dependency versions, measured errors, support, wall time and peak Python allocations from tracemalloc. Measurements include tracing overhead. They exclude reference generation and replay; they do not measure whole-process RSS. The uniform control exercises the cost of scanning when every entry must survive.
