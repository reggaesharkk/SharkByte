# Audited high-support scaling

This is an opt-in CPU experiment for measuring populated-state support and resource use. It does not change the default simulator, raise the public CLI's qubit limit, provision cloud infrastructure, or treat a register width as evidence that its full statevector was computed.

## What the workload labels mean

| Family | Work performed | Expected support behavior |
| --- | --- | --- |
| `basis-walk` | Seeded sequence of X, Z, and CX signed basis permutations | One populated coordinate at every width |
| `connected-ghz` | H followed by a connected CX chain | Two populated coordinates; a connected entangled state |
| `growing-support` | H on each qubit | Full support of `2^n` coordinates |
| `interference` | H-Z-H on one qubit, followed by connected CX gates | Two coordinates transiently, one after destructive interference |
| `uncomputation` | Full H layer, controlled phase, its inverse, and reverse H layer | Full transient support; exact adjacent inverse simplification reduces the source stream to zero executed gates |
| `dense-no-benefit` | Full H layer followed by Z on every qubit | Full support with alternating signs; inverse simplification retains every gate |

The generated circuit and the complete original gate list are included in each case receipt. A simplified gate count is a source-level algebraic result, separate from the number of amplitudes actually evolved. For `uncomputation`, the sparse engine's floating-point forward/inverse run is compared to independent numerical backends only at the configured small widths. The simplified circuit represents the exact ideal unitary identity; it is not claimed to reproduce every rounding residual from the unsimplified execution.

## Ladder, measurements, and refusal policy

The default ladder is 12, 16, 20, 24, 28, and 30 qubits. The 30-qubit controls run only when their calculated peak-support plan fits the worker limit. Full-support families are refused before process launch when their sparse estimate plus worker reserve exceeds the configured cap. The runner never allocates a vector just to test whether a planned workload fits.

The primary sparse engine always stores a dictionary of its populated coordinates. If that dictionary contains `2^n` entries, it represents the complete statevector even though it is not a dense contiguous array. The receipt separately records register dimension, nonzero support, whether support fills the register, and whether a dense array was materialized by the primary engine. No amplitudes are injected from an analytic formula; analytic formulas are references against which computed sparse entries are checked.

Each successful worker reports:

- process CPU time and wall time for sparse evolution, exact simplification, and adaptive comparison where applicable;
- OS peak resident working set on Windows or peak RSS via `getrusage` on Linux, distinct from Python `tracemalloc`, estimated sparse bytes, and Windows Job committed memory;
- support after each gate, peak/final populated states, state digest, and probability sum;
- complete complex-vector comparison with NumPy, Qiskit, and Cirq through the selected reference width;
- analytical support/amplitude checks at larger widths, explicitly labeled as analytic rather than independent numerical backend comparisons;
- source module hashes, exact seed, worker limit, containment method, receipt digest, and replay result.

Three repeated runs use the same seed and circuit. Each timed kernel is repeated internally until at least 50 ms of process CPU time has accumulated, then divided by the iteration count; this avoids reporting Windows ARM64's process-time reporting quantum as a misleading zero for tiny controls. The receipt records the inner iteration count. Timing and resident-memory values are machine measurements, not portable guarantees. `512` bytes per sparse amplitude is a planning estimate, not observed memory. The runner's separate `96` bytes per basis planning reserve is a conservative dense-reference estimate, not a measured bound.

Windows workers are created suspended in the existing Job Object supervisor with a committed-memory ceiling and kill-on-job-close. Linux workers use an external parent timeout and `RLIMIT_AS`, which limits virtual address space and is not an RSS or physical-memory limit. If the OS, memory inventory, supervisor, parsing deadline, or atomic publication path is unavailable, the run fails closed. Peak RSS comes from OS process accounting; it is not inferred from Python allocation tracing.

## Reproduction

From the checkout root, with NumPy, Qiskit, and Cirq installed for all three independent checks:

```powershell
python -B tools/high_support/frontier_scaling.py `
  --output evidence/frontier-scaling-2026-11-20/windows-arm64/frontier.json `
  --qubits 12 16 20 24 28 30 --repeats 3 --seed 20261120 `
  --memory-mib 1536 --worker-seconds 90 --max-total-seconds 1800 `
  --reference-qubits 12 --reference-backends numpy,qiskit,cirq `
  --include-compaction
python -B tools/high_support/verify_frontier_scaling.py `
  evidence/frontier-scaling-2026-11-20/windows-arm64/frontier.json
```

The runner publishes a new receipt atomically and refuses to overwrite an existing destination. It includes a 30-minute total wall-time safeguard by default. It does not contain a cloud client and will not start, resize, or stop a Google Compute Engine VM. A timeout limit bounds worker time, not cloud cost in dollars; researchers must use the actual region and machine's hourly rate to compute their own maximum charge.

For Colab, clone the exact feature-branch commit into a fresh runtime, install the versions recorded in `requirements-independent-quantum.txt`, use a worker limit no larger than 2 GiB, and set a total runtime limit of at most 30 minutes. Save the generated receipt and verifier output before disconnecting the runtime.

For the existing 32-GiB GCE machine, use a worker limit no larger than 8 GiB, keep the default 90-second per-worker timeout, and set `--max-total-seconds 3600` or lower. Do not create another VM. Record the machine type, region, hourly price, attached disk, and actual runtime alongside the receipt. The runner's Linux containment is an address-space limit, so the measured peak RSS and the configured address-space cap must be reported separately.

The CPU-cost safeguard is intentionally a wall-time and per-worker cap, paired with no automated cloud provisioning. It cannot determine or guarantee a USD charge without the researcher's current billing configuration.

## Compaction and optimization interpretation

The `compaction-helpful` control starts with a normalized dominant branch and 255 legitimate, tiny nonzero coordinates; exact cumulative L2 budgeting can remove those coordinates while a replay verifier checks the certificate. The `compaction-no-benefit` control has equal large coordinates, so no deletion is permitted; candidate evaluation and certificate bookkeeping measure overhead with no support reduction. These are one benchmark pair, not evidence of a universal speedup.

The `dense-no-benefit` family measures the adaptive backend on full support and records every representation transition. A dense transition may reduce evolution time at some widths or add conversion and allocation costs at others. No speedup is claimed without repeated measurements from the corresponding receipt. Cases refused by the plan are `UNSUPPORTED` for that machine budget, not failures of circuit correctness.

## Evidence boundaries

Decision labels apply to individual cases. `PASS` means that the worker completed under its configured limit and its analytic checks passed; independent backends are listed separately. `UNSUPPORTED` means the run was refused before allocation or a requested reference was unavailable. `FAIL` means an execution, analytic comparison, independent reference, or verifier failed. No conclusion here converts sparse support into a full `2^n` statevector claim. Full-vector verification is explicitly limited to the widths written in the receipt; larger cases use separately labeled closed-form checks.
