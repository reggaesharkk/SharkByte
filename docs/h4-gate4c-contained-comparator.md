# H4 Gate 4c — OS-contained comparator (research)

This opt-in command places the **existing Gate 4b independent candidate-v1 comparator** inside an OS-limited child process. It does not change `tools.high_support.h4_compatibility`, the pinned historical candidate, mathematical verification, or the public signed-permutation certificate interface. **Hadamard remains unsupported in the public certified API.**

## Run

From a **trusted full-history** SharkByte checkout (the pinned candidate-v1 commit must be present):

```sh
python -B -m tools.high_support.h4_compatibility_contained --memory-mib 256 --seconds 90 sharkbyte-xz-cx-h-candidate-v1 evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json sharkbyte-xz-cx-h-candidate-v1 evidence/h4-candidate/source.json evidence/h4-candidate/receipt.json
python -B -m unittest tests.test_h4_gate4c_containment -v
python -B -O -m unittest tests.test_h4_gate4c_containment -v
python -B -OO -m unittest tests.test_h4_gate4c_containment -v
```

Exit codes retain Gate 4b's meanings: **0 COMPATIBLE, 1 NOT_ESTABLISHED, 2 INVALID_RECORD, 3 UNSUPPORTED**. A compatibility result concerns two independently replayed candidate certificates. Accuracy within each source's requested budget is reported separately; it is not inferred from compatibility. The output is one JSON line containing the comparison and resource-policy metadata. Unknown versions fail closed.

The parent snapshots at most 32 KiB per source and 4 MiB per receipt into a temporary directory, preserving **exact input bytes** and binding their SHA-256 digests. Only local regular-file inputs are accepted; directories, symlinks, FIFOs and device nodes are refused before reading. The parent compares the opened descriptor with the pre-open file identity and checks size and modification time across the bounded read. Linux additionally requests nonblocking, no-follow open. Hostile concurrent writers, Windows pre-open substitution, and malicious filesystem servers remain outside this contract. It does not import or execute the H4 arithmetic comparator. Its contained worker independently checks source/receipt syntax, archival content, ideal prefixes, binary64 words, charges, budgets, outcomes and the two traces. The parent reads at most 8 KiB of worker output after termination and checks decision/exit-code agreement. There is no published comparison file; only the completed JSON outcome is printed to stdout.

## OS enforcement and trust boundaries

- **Windows (x64 / ARM64):** an opt-in Windows Job Object is created with the requested outer *job-wide commit* cap, an empirical lower inner cap, mandatory process association at creation, and suspended worker startup. Membership is verified before resume. `KILL_ON_JOB_CLOSE` and a common external deadline govern the comparator and its descendants. The supervisor verifies job cleanup and reports peak job committed memory. If peak telemetry exceeds the outer cap, it refuses the result even when the allocation itself failed. This condition was observed in the native exhaustion probe and is not evidence of a hard peak-commit guarantee. When job assignment, limits, cleanup or the deadline fails, the result is UNSUPPORTED. This path reuses the separately tested `tools.high_support.windows_job` implementation.
- **Linux / Ubuntu WSL2:** the worker and its fixed historical Git subprocesses inherit the OS-enforced `RLIMIT_AS` *per-process address-space cap*. The worker starts in a separate process group, and the parent keeps the group leader unreaped until it has signalled the group and checked for live members in Linux procfs. Dead descendants may remain as zombies until their adopting process reaps them. This is **not an aggregate cgroup memory limit**. There is no claim that a malicious executable unable to stay in its process group is contained. Future untrusted-service exposure needs a cgroup/namespace-based or equivalent external supervisor.
- **Unsupported systems:** refuse without launching the comparator. Default resource policy: 256 MiB and 90 seconds. Memory policy may be set to 32..1024 MiB, wall time to (0,180] seconds. Low caps may cause conservative UNSUPPORTED outcomes. The comparison's existing cooperative 20-second replay deadline per side remains in place as an additional check.

A malicious receipt is treated as **data**, not executable code. The worker executes **trusted repository Python and the pinned, hash-checked historical Git tree**. This is a resource-limited engineering boundary, not a general arbitrary-code sandbox, privilege isolation, filesystem sandbox, software-supply-chain attestation or operator authentication. A Git hash and source digest do not authenticate where or by whom a computation ran.

## Acceptance evidence and limitations

- CI must run native contained replay and adversarial source/receipt tests on hosted Windows x64 and Linux under normal Python, `-O`, and `-OO`. Native Windows ARM64 and Ubuntu WSL2 reproduction must be reported separately; hosted Windows x64 is not ARM64 evidence.
- Boundary tests cover unknown candidate versions, bad receipt bindings, oversized input refusal before spawn, tiny wall deadlines, and rejection of inconsistent child outcomes. They must also prove direct comparator logic is not invoked in the parent.
- The existing Gate 4a and 4b archived records are unchanged. The Gate 4c verifier does not register candidate-v2 and does not supply a cross-version equivalence theorem.
- Linux per-process RLIMIT is not a tree-wide memory guarantee. Native Windows commit peaks, nested jobs and VM policies remain workload- and OS-dependent. Child process exit does not by itself prove execution authenticity.
- Deadline measurement includes input copying, child execution, and result inspection, but normal cleanup or command-line printing can extend wall time. Hostile concurrent filesystem writers, crash durability, and OS-level external attestation remain OPEN.

This design is **Gate 4c engineering evidence**, not authorization to widen public Hadamard certification claims.

## Native hostile review observations

[Native run record](../evidence/h4-gate4c-native/validation.json) binds the tested implementations, test source and original inputs. The identical v1 fixture returned COMPATIBLE on both native ARM64 hosts. The hostile suite exercises all four CLI outcomes, bounded input refusal, Git history and manifest integrity, actual allocation refusal, a started worker timeout and a direct worker exiting while its child still runs.

Linux group teardown now reserves the leader PID through signalling and confirms no live members before reaping it. This covers descendants remaining in the group. On Windows a descendant process handle was once still unsignalled immediately after job accounting reached zero. The regression requires bounded signalling, with a two-second observation window. This supports termination in the tested cases, while instantaneous handle signalling remains unproved. The Windows allocation refused 96 MiB with a 64 MiB cap, but its peak telemetry reported 108,593,152 bytes. The launcher rejected the result. The strict observed-peak ceiling failed this check, even though allocation refusal and fail-closed behavior passed.
