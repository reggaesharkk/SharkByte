# Audited high-support scaling — evidence index

**Scope:** opt-in CPU measurement only. Default simulator behavior and qubit limits are unchanged. No Colab runtime or billable cloud VM was started.

## Source revision and receipt integrity

The new Windows ARM64 and Ubuntu WSL2 ARM64 runs used source commit `806ee56c3a262774173adfdd31266dce55c9e64e`, on feature branch `research/audited-high-support-scaling-20261120` based on main `07188305ef8c57f72b6a4934296d88a979c0ba39`. Each receipt includes the full source module hash map and its own canonical `record_sha256`. SHA-256 below is over the receipt file bytes.

| Platform / record | Source revision | File SHA-256 | Record SHA-256 | Size |
| --- | --- | --- | --- | ---: |
| Windows ARM64, historical `windows-arm64/frontier.json` | `ee562ed3e25a9eb719d890b7a1c12e96bd3c3a8b` | `f843c47a9b8cfc72f04b0423bd83c9865247a6a5f61443e55584216775e1c66` | `75512323411633ae197b1114df30c3065e59a2eef226c35fa35599bf6e8cc566` | 4,016,364 B |
| Windows ARM64, clarified `windows-arm64/frontier-v2.json` | `806ee56c3a262774173adfdd31266dce55c9e64e` | `6db709749c9b867eb4c48a4331bd74be5168d7c02ed013b9bffa9f5e8eb73c2b` | `5fe28348d97945da91f1b3f20efe3743770349e148867f8344822b26bcb1c9d4` | 4,020,420 B |
| Ubuntu WSL2 ARM64, `ubuntu-wsl2-arm64/frontier.json` | `806ee56c3a262774173adfdd31266dce55c9e64e` | `a605acb62b9a94c7747c436b075b7660709c96bae53d794519aa4c68893c1744` | `c56f8390a50469c68fe56558156818135cc752df69d7b3bf76ac5e8f243b8658` | 4,018,869 B |

The first Windows record predates the wording fix that distinguishes a dense array from a complete sparse dictionary. It remains unchanged and replays against its recorded source commit. The current verifier accepts its legacy storage field only for that source revision and independently derives support completeness from the recorded support count and register dimension.

Current source SHA-256 values:

| Source module | SHA-256 |
| --- | --- |
| `benchmarks/sb_quantum_benchmark/bounded_support.py` | `f7f00a5ee689e93003ff03e50a1e93e1b1d4c8fd77665cd9e42eb942aa1b1ab9` |
| `benchmarks/sb_quantum_benchmark/certified_support.py` | `88b8245fad744c7b3fc3ad7ab156808f7f256eca396f567dc51e01dc01aef52d` |
| `benchmarks/sb_quantum_benchmark/frontier30.py` | `279ad305ded37f143d0319770d18e8f4164b10e6b8838cff270072a88a5936ca` |
| `benchmarks/sb_quantum_benchmark/sparse_backend.py` | `186aad8bed0b0c0ff13efc642fe284a6d1fc9cccdd2c36174b434b6ddbe8572c` |
| `tools/high_support/adaptive_statevector.py` | `821f5938ae7218e76e9f8c69fd0550ee6a348cec0f4ac2d1363edf66055c799c` |
| `tools/high_support/dense_statevector.py` | `18b08f2fe1ed11f18c1b7872b2ab7ae96fe744e0a8f01fd0bb238e7686722ac9` |
| `tools/high_support/frontier_scaling.py` | `06f2035d7bd65cf27eb9df16c40c2c1d653104cb9158a29542d58096bd8a043e` |
| `tools/high_support/verify_frontier_scaling.py` | `2979f465d8eaa43bdf352b6455ebc4637afc23893589ab51e9ad08e8dcf7592f` |

The two previously untracked adaptive receipts were left byte-for-byte unchanged and are not part of these scaling records:

| File | SHA-256 |
| --- | --- |
| `auto-budget-20261118-224835.json` | `265ed1aa4a4b7d8a4a1ebb02e8cfdbd85400f21ba9f428d6862b696c5816ff82` |
| `auto-dense-20261118-224626.json` | `88df08858c9e4f94a91328ea88cf2fe85c542a1cbfee481956ea1071bcd14f75` |

## Reproduction and verification

Both current platform runs used seed `20261120`, three repeated executions per case, a 1.5-GiB worker cap, a 90-second worker deadline, a 1,800-second total deadline, a 12-qubit independent dense-reference limit, and the default support-plan refusals. The complete original gate streams, support trajectory after each gate, timing iterations, per-case peak resident memory, Windows Job Object peak committed memory, backend decisions, sparse state entries when bounded, and exact compaction certificates are stored in the JSON receipts.

Per-case peak resident memory is the OS process high-water across that worker's whole case, including any adaptive/reference or certificate work performed there; it is not attributed to one engine. For the scaling table, kernel CPU/wall times are medians across the three repeated runs, while the reported peak resident value is the maximum across those runs. Windows Job committed bytes are supervisor measurements and are reported separately from resident memory.

From the source checkout:

```powershell
python -B tools/high_support/frontier_scaling.py --output evidence/frontier-scaling-2026-11-20/windows-arm64/frontier-reproduction.json --qubits 12 16 20 24 28 30 --repeats 3 --seed 20261120 --memory-mib 1536 --worker-seconds 90 --max-total-seconds 1800 --reference-qubits 12 --reference-backends numpy,qiskit,cirq --include-compaction
python -B tools/high_support/verify_frontier_scaling.py evidence/frontier-scaling-2026-11-20/windows-arm64/frontier-reproduction.json
```

On Ubuntu WSL2 ARM64, use the same arguments with `python3 -B` and write to `evidence/frontier-scaling-2026-11-20/ubuntu-wsl2-arm64/frontier-reproduction.json`. Linux uses the existing `RLIMIT_AS` plus parent wall timeout. `RLIMIT_AS` is a virtual address-space ceiling, not an RSS or physical-memory ceiling. Windows uses a Job Object committed-memory ceiling and kill-on-close. These memory quantities are not interchangeable.

The exact replay commands used for the archived records are:

```powershell
python -B tools/high_support/verify_frontier_scaling.py evidence/frontier-scaling-2026-11-20/windows-arm64/frontier.json
python -B tools/high_support/verify_frontier_scaling.py evidence/frontier-scaling-2026-11-20/windows-arm64/frontier-v2.json
python -B tools/high_support/verify_frontier_scaling.py evidence/frontier-scaling-2026-11-20/ubuntu-wsl2-arm64/frontier.json
```

All three verifier replays returned **PASS**, each checking 29 completed cases and independently validating 9 pre-run full-support refusals. No state array was allocated for a refused case. The first receipt is replayed using source files read from its source commit; the other two are bound to `806ee56…`.

## Environments

| Host | CPU architecture | Python | CPUs | Physical/guest memory reported | Peak resident metric |
| --- | --- | --- | ---: | ---: | --- |
| Windows 11, native ARM64 | ARM64 Snapdragon X126100 / Oryon | CPython 3.12.10, NumPy 2.5.3 | 8 | 16,758,587,392 B physical; 5,262,495,744 B available at run | Windows `PeakWorkingSetSize` |
| Ubuntu WSL2 | aarch64 Oryon | CPython 3.14.4, NumPy 2.3.5 | 8 | 8,106,524,672 B guest; 6,809,464,832 B available at run | `getrusage(RUSAGE_SELF).ru_maxrss` |

NumPy was available in both local environments. Qiskit and Cirq were not installed, so their local reference results are explicitly **UNSUPPORTED**. The source workflow installs the pinned libraries and requires all three references on GitHub-hosted Windows x64 and Ubuntu x64 at 12 qubits. Those CI machines are not ARM64 evidence. GitHub PR status is reported separately from local results.

## Results and boundaries

| Workload / width | Windows ARM64 | Ubuntu WSL2 ARM64 | Decision and interpretation |
| --- | --- | --- | --- |
| `basis-walk`, 30q | support 1, median evolution 0.119 ms | support 1, 0.089 ms | **PASS**; one populated coordinate, not a 30q vector |
| `connected-ghz`, 30q | support 2, 0.083 ms | support 2, 0.046 ms | **PASS**; connected entangled two-entry state, not a 30q vector |
| `interference`, 30q | peak support 2, final 1, 0.084 ms | peak 2, final 1, 0.047 ms | **PASS**; destructive interference; not a full vector |
| `growing-support`, 20q | 1,048,576 entries, median 0.598 s, peak resident 345,333,760 B | 1,048,576 entries, 0.543 s, peak resident 359,038,976 B | **PASS**; complete statevector represented by a sparse dictionary; analytic checks, not an independent full-vector reference at this width |
| `uncomputation`, 20q | peak 1,048,576, final 1; original evolution 1.456 s; source simplifies to 0 gates; simplifier + empty-circuit path ratio 33,772× | peak 1,048,576, final 1; 1.120 s; 0 gates; ratio 550,798× | **PASS for this exact circuit**; exact algebraic cancellation. Ratios are implementation and timer measurements for the zero-gate identity case, not a general speedup claim |
| `dense-no-benefit`, 20q | support 1,048,576; sparse 3.866 s vs adaptive dense 0.186 s; peak resident 479,313,920 B | support 1,048,576; sparse 2.622 s vs adaptive 0.091 s; peak resident 527,118,336 B | **PASS**; adaptive dense path was 20.8×/28.9× faster for this full-support case only; the inverse simplifier retained the circuit |
| `compaction-helpful`, 9q | support 256→1; 2.00 ms baseline vs 11.14 ms compact; 11,071 B cert; 6.58 ms replay | 256→1; 1.25 ms vs 7.86 ms; 11,071 B cert; 4.00 ms replay | **PASS** exact rational replay; legitimate small inputs removed within L2 budget `1e-8`; compaction was 5.6×/6.3× slower end-to-end here |
| `compaction-no-benefit`, 9q | support 256→256; 2.14 ms vs 23.19 ms; 598 B cert; 11.84 ms replay | 256→256; 1.30 ms vs 14.46 ms; 598 B cert; 7.54 ms replay | **PASS** with zero deletion; compaction was 10.8×/11.1× slower here |
| Full-support `growing-support`, `uncomputation`, `dense-no-benefit`, 24/28/30q | 9 pre-run refusals | 9 pre-run refusals | **UNSUPPORTED** under the 1.5-GiB plan; no worker allocation was attempted |

For q20 uncomputation, the exact deletion/rounding certificate is not what establishes inverse simplification: the simplifier proves an ideal gate-stream identity. The unoptimized floating-point path can retain tiny residuals, while the simplified empty stream has exact ideal output. The receipt keeps those measurements separate. At q12, the complete 4,096-entry sparse states were compared against dense NumPy with maximum complex-amplitude difference 0 for five families and `2.43e-18` for uncomputation. Qiskit/Cirq were unavailable locally; GitHub CI covers all six q12 families and compaction controls with required NumPy/Qiskit/Cirq references.

The helpful compaction case's exact replay bound is `685851277/429496729600000000` (about `1.60e-9`) under a requested budget `1/100000000`; the verifier recomputes it with exact `Fraction` arithmetic. The event deletes 255 coordinates. No-benefit compaction deletes none. This is deletion-only mathematical accounting for the already rounded binary64 inputs under signed-permutation gates; it is not end-to-end error certification for arbitrary gates or environments.

## Separate cloud and mathematical frontier

No scaling experiment ran on Colab or GCE. The attached archived 32-GiB GCE audit verifies moving-branch evidence at source revision `7793d5e…`; it explicitly does not rerun or resource-stress the VM. Cloud execution remains **OPEN** pending user authorization. Prepared commands use worker caps of at most 2 GiB for Colab and 8 GiB for the existing GCE machine, bounded worker and total wall time, and no provisioning API. The wall-time cap is not a USD cost guarantee.

Hadamard end-to-end certification is a separate **OPEN** proof obligation, detailed in [the proof note](../../docs/hadamard-certification-proof-obligations.md). The note derives the exact `Q(√2)` route and lists the coefficient, arithmetic, subnormal, deletion-ledger, and normalization obligations. No approximate Hadamard certification was implemented.

## Acceptance decisions

| Criterion | Decision |
| --- | --- |
| Main synchronization, preserved branches/evidence and exact base commit | **PASS** |
| Default simulator behavior unchanged; experiment opt-in | **PASS** |
| Source-bound generation receipts and independent replay | **PASS** |
| Windows ARM64 and Ubuntu WSL2 full local test suite | **PASS**; 154 tests Windows (no skips), 154 tests WSL2 (14 skips: optional SciPy and Windows-only Job Object tests) |
| 12q complete-vector NumPy comparisons | **PASS** |
| Local Qiskit/Cirq comparisons | **UNSUPPORTED** (not installed); GitHub CI required to close hosted comparison |
| 16q/20q analytic sparse-state checks | **PASS** for listed generated families; no claim of independent full-vector verification |
| 30q low-support controls | **PASS** for support 1/2 only |
| 24q+ full-support workloads under 1.5 GiB | **UNSUPPORTED**, fail-closed before worker launch |
| Compaction performance improvement | **FAIL** for both measured compaction controls (slower); exact deletion replay **PASS** |
| General dense adaptive speedup | **OPEN**; measured faster only on the listed full-support no-benefit cases |
| Colab/GCE scaling execution | **OPEN**, no cloud runtime started |
| Hadamard end-to-end numerical certification | **OPEN**, not implemented |
