# Bounded support audit

Base commit `9dce751e3660ae54a108acabf2a00c8b72be23ca`. The numerical and scaling record is [bounded-audit.json](../evidence/bounded-audit.json). It contains implementation digests, exact gate-list digests, seeds, environment versions and all observations. [Linux limit checks](../evidence/bounded-audit-limits.json) bind the original source and generated receipt by SHA-256.

| Criterion | Decision and evidence |
|---|---|
| 1. Deletion bound and ledger | PASS for ideal unitary propagation of the recorded perturbations. Each removal is a coordinate projection with exact squared distance equal to the sum of squared real and imaginary parts deleted. For tick size t, charge k satisfies (k-1)^2 t^2 < mass <= k^2 t^2. Taking the integer square root of the floored rational quotient produces the floor of its real square root. The conditional increment yields the ceiling. Each prefix costs at most the remaining ticks, so induction bounds total charge by B. Unitarity and the triangle inequality propagate the sum of event distances. Adding a local floating-point gate defect at each step adds its norm to that bound. No local roundoff bounds were proved. |
| 2. Randomized circuits | PASS for 12 deterministic circuits, 48 schedules. Widths 2, 4, 7, four seeds each, eight gate families, budgets 1e-8 and 1e-3, intervals 1 and 7. |
| 3. Numerical edge cases | PASS for the coherent-rotation, interference-return and protected-branch controls, adjacent binary values at a tick boundary, repeated pruning and minimum positive subnormal. Exact component squaring avoids floating underflow in the deletion charge. |
| 4. Full-vector comparisons | PASS on the seeded set. Each reference pair in the JSON is [original sparse versus reference, compacted versus reference]. Paired delta compares the two sparse executions and includes any differences in subsequent kernel rounding. The comparison allowance of 1e-13 is empirical. |
| 5. Replay | FAIL on inspection of the original minimum-charge and event-schedule checks. Repaired. Regression checks PASS for overcharge, undercharge, reordering, repeated indices, malformed components, wrong source digest and cumulative ledger. Exact component replay of the archived five cases succeeded on both ARM64 environments. The verifier checks the supplied witness and its budget. It does not authenticate the author or prove the generator selected the maximal prefix. |
| 6. Protection | PASS for fixed coordinates. A small amplitude protected at index 1 moves to index 3 under X on qubit 1 and can then be deleted. A guarantee for that moving physical branch would be false. |
| 7. Scaling | PASS for bounded experiments at 8, 12, 16 and 20 qubits. Each baseline and compacted case runs in its own process. The record includes support after completed gates, lifetime peak RSS, traced peak allocations, serialized certificate bytes and one traced wall time. At 16 and 20 qubits the 8192-entry safety cap refused both uniform runs and the original product runs. Full-support performance above that cap is OPEN. |
| 8. Resource enforcement | The original implementation checked the clock only after compaction and replay restarted it per gate. Candidate ordering now uses interruptible heap operations and replay shares one deadline. Estimated workspace charges remain estimates. Linux supervisor PASS covers startup through serialization or parsing with an OS address-space limit and wall deadline. Native Windows hard process containment is OPEN. Individual Python arithmetic operations and allocations have no preemptive in-process deadline. |
| 9. Regression environments | Native Windows ARM64 and Ubuntu WSL2 each passed 114 tests. The PR workflow repeats the bounded tests, reference comparisons and Linux process limit controls. |
| 10. Reproduction | PASS for the checked-in workload definitions, exact reference versions, receipts and commands below. Runtime, RSS and cross-platform transcendental results depend on the environment. |

The 12-qubit small-rotation product retained one entry and completed in 1.56 ms, compared with 87.54 ms for the 4096-entry baseline. The uniform circuit retained all 4096 entries and took 93.17 ms compared with 63.49 ms. Tracing contributes overhead. Worker timings exclude JSON serialization; certificate sizes measure serialized payload and the process-limit check includes serialization.

## Reproduction

From the repository root in an environment with the pinned numerical dependencies:

```sh
python -m pip install -r requirements-high-support.txt
python -m unittest discover -s tests -v
python tools/high_support/check_bounded.py
python tools/high_support/audit_bounded.py > local-audit.json
# Linux only
python tools/high_support/check_bounded_limits.py > local-limits.json
```

The limit control regenerates the 17-qubit witness in a temporary directory and replays it. Its RSS can exceed the sparse kernel estimate because Python objects, allocator overhead and the receipt parser also occupy memory. The supervisor limits the child process's virtual address space and publishes its output only on success.

The original interference control now exercises the 128 KiB kernel-only budget as a required workspace refusal. Its full-vector comparison uses 512 KiB for kernel, candidates and witnesses, with the original numerical acceptance criteria.

## Moving-branch protection follow-up

The archived protection counterexample remains a valid finding about fixed indices: the initial component at index 1 moves to index 0 under X(0), and the fixed `protected=(1,)` mode can delete it. The new opt-in `protected_branches=(1,)` mode follows that initial coordinate and retains index 0. It is limited to x, z, and cx gates; mixing operations are rejected. Its semantics identifier is distinct, and the exact Fraction verifier independently propagates the coordinate map and checks every deletion event. Fixed-mode receipts and certificates retain their prior schema and meaning.

The feature-specific, source-bound mapping and overhead records are in `evidence/moving-branch-protection-windows-arm64.json` and `evidence/moving-branch-protection-ubuntu-wsl2-arm64.json` when present. Full-suite records are `evidence/moving-branch-protection-full-tests-windows-arm64.json` and `evidence/moving-branch-protection-full-tests-ubuntu-wsl2-arm64.json`. Current acceptance decisions are recorded in those artifacts. Exhaustive evidence covers every legal single x/z/cx gate and every initial basis coordinate through four qubits, and enumerates the full affine coordinate-permutation closure generated by x and cx through four qubits, checking 5,160,960 basis images. Randomized longer circuits extend through 20 qubits. This does not prove behavior through mixing gates, physical branch semantics, or a general performance gain.
