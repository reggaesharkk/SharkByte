# Windows job containment for bounded support

From the repository root on 64-bit Windows with CPython 3.12, use fresh destination names on a local filesystem. A successful generation includes a separate replay before publication. The verify operation publishes a JSON verification result containing the digest of the receipt it replayed.

```powershell
python -m tools.high_support.limit_bounded_windows --commit-mib 512 --seconds 180 generate examples/high_support/roundtrip_17q.sbq roundtrip.json --budget 1e-10 --interval 214 --support-cap 131072 --memory-mib 256 --seconds 180
python -m tools.high_support.limit_bounded_windows --commit-mib 512 --seconds 180 verify examples/high_support/roundtrip_17q.sbq verified.json roundtrip.json
python -m tools.high_support.check_windows_bounded --architecture ARM64 --output local-arm64.json
python -m unittest discover -s tests -v
```

The supervisor emits a diagnostic summary and exits nonzero on failure. A unique sibling directory holds the diagnostic log and job accounting. Temporary receipt data is removed after normal supervisor cleanup. Use a trusted checkout, interpreter and destination directory. Atomic publication uses a same-volume Windows rename that refuses an existing destination. Verification snapshots the input receipt inside the limited worker. Generation, verification and publication run sequentially against one absolute deadline. Teardown and recording diagnostics can extend the elapsed time beyond that deadline.

## Hostile audit decisions

| Criterion | Decision and evidence |
|---|---|
| 1. Baseline and scope | PASS. Based on merged audit commit 1c7c9f4b508ebc5299687a3662d1195b51e06a97. The supervisor is an opt-in module. |
| 2. Assignment before execution | PASS. Both jobs are configured and read back first. CreateProcessW receives a mandatory job list and CREATE_SUSPENDED. IsProcessInJob checks both memberships before ResumeThread. A failed job attribute or process creation has no fallback launch. |
| 3. Memory, lifetime and deadline | PASS for the recorded operations. The outer job uses the caller's JOB_MEMORY threshold and KILL_ON_JOB_CLOSE. An inner job reserves headroom for refusal. PeakJobMemoryUsed, both configured thresholds, worker exit status and elapsed time are recorded. An external wait also covers the publisher. |
| 4. ABI, descendants and cleanup | PASS on tested 64-bit environments. Handles and SIZE_T use pointer width. Layout sizes are checked. No handles are inherited, and no breakaway flag is enabled. Regressions launch a real surviving descendant, terminate the tree, and test last-handle closure on a suspended worker. Hosts whose enclosing jobs reject this hierarchy must refuse execution. |
| 5. Publication | PASS for tested local same-volume publication. A completed staging file is independently replayed and closed before a separate publisher renames it. Invalid input, a preexisting destination and expiry during publication are tested. Rollback uses file identity to distinguish this run's result. |
| 6. Failure repetition | PASS. The native matrix exercises ten memory refusals and ten timeouts for each operation. Each requires no destination, a verified job assignment, zero active processes after termination and a recorded outer peak within the requested ceiling. |
| 7. Measurements | PASS. Peak job commit is queried from extended limit information. Active process count and total processes come from job accounting. Python MemoryError is mapped to exit 86; unrelated nonzero exits are reported separately. |
| 8. Fixture | PASS. The original 214-gate source produced final support one, with one deletion event. The existing verifier replayed the complete witness in another process. The standalone verify operation independently consumed the published bytes. Linux reproduced its archived receipt hash. Windows and Linux receipt hashes differ. |
| 9. Regressions | Windows ARM64 passed 119 tests. WSL2 passed all 114 applicable tests and skipped five Win32 lifecycle tests. The original Linux six-case limit matrix passed. Hosted x64 has its own architecture assertion, workflow and evidence artifact. |
| 10. Provenance | The ARM64 record binds the worker, supervisor, matrix, simulation code and fixture by SHA-256. Each case includes publication outcome, elapsed time and cleanup accounting. The PE header and reported machine type identify the native interpreter. |

## Failed experiment and remaining limits

A single job configured at 33,554,432 bytes returned MemoryError with a reported peak of 34,578,432 bytes. Detached creation removed the console host and a repeat still reported 38,182,912 bytes. These observations rule out using the programmed threshold as proof that every reported peak is below it. The inner threshold is lower than the outer threshold by the smaller of 12 MiB and half the requested budget. Both limits are read back and recorded. This choice can refuse useful work earlier. The outer peak check remains an acceptance criterion. The tested margin is empirical; arbitrary allocation patterns and other Windows builds remain OPEN.

Job accounting covers processes in the assigned tree. Interpreter startup before the supervisor itself starts, the supervisor's own memory, disk space, unrelated services and malicious modification by another user process are outside the contract. A killed supervisor can leave private staging files or a fully validated receipt if it dies during the final rename. Crash durability, simultaneous hostile directory writers and real-time scheduling guarantees remain OPEN. Cleanup after a timed-out publisher can briefly leave a *complete*, validated file visible before rollback. No streaming partial file is published.

Win32 structure and nesting semantics are documented by Microsoft in [extended job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information) and [nested jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs).

Both 42-case records use implementation commit `0b58b56e53d4e59ff0f84beec87b33a47531350d`. Criterion 9 PASS on native ARM64 and [GitHub-hosted x64](https://github.com/reggaesharkk/SharkByte/actions/runs/44543016537). Criterion 10 PASS for source binding and replay within each recorded environment. See the separate [ARM64 measurements](../evidence/windows-job-arm64.json) and [x64 measurements](../evidence/windows-job-hosted/windows-job-x64.json). All recorded implementation digests match the checkout on both machines. The native generation peak was 92,323,840 committed bytes in 25.953 seconds, including validation and publication. Standalone verification peaked at 81,465,344 bytes in 11.406 seconds.
