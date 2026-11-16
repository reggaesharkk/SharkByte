# SharkByte

![SharkByte Studio and the 16,777,216-active-state terminal benchmark.](docs/sharkbyte-studio-banner.svg)

SharkByte is an experimental programming language and CPU simulation toolchain. Write and run `.sb` programs in a local browser workspace or from the terminal, inspect the results, and save JSON receipts with the exact source.

[Start Studio](#sharkbyte-studio) · [Try error correction](#five-qubit-phase-flip-recovery) · [See the 16-million-state results](#scaling-to-16777216-active-states) · [See connected-circuit verification](#connected-circuit-verification) · [Cite SharkByte](#cite-sharkbyte)

| What to try | Where it runs | What you can reproduce |
| --- | --- | --- |
| Phase-flip recovery | Studio, Quantum mode | Five qubits and eleven cases, including single-error recovery and two-error failure controls |
| Million-state benchmark | Studio, built-in preset | 40 qubits, 52 gates, and 1,048,576 active states. A browser-launched run took 3.020 s of CPU evolution. |
| 16-million-state benchmark | Studio or terminal, bounded sparse worker | 40 qubits, 56 gates, and 16,777,216 active states; historical standalone runs are recorded for Windows ARM64 and Ubuntu WSL2 |

## SharkByte Studio

Download and extract the GitHub source ZIP or clone the repository. From the checkout, use Python 3.10 or later:

| Platform | Command |
| --- | --- |
| Windows PowerShell | `python -B sharkbyte_studio.py` |
| Linux or WSL | `python3 -B sharkbyte_studio.py --no-browser` |

Open [http://127.0.0.1:8120/](http://127.0.0.1:8120/). Studio listens on your own computer. Keep the terminal running and press Ctrl+C to stop it. If the port is busy, pass `--port 8121` and open the URL printed by the launcher.

To try the 16-million-state preset while [PR #9](https://github.com/reggaesharkk/SharkByte/pull/9) is in review, select `codex/studio-16m-adaptive` on GitHub before downloading the source ZIP, or clone that branch directly:

```text
git clone --branch codex/studio-16m-adaptive https://github.com/reggaesharkk/SharkByte.git
cd SharkByte
python -B sharkbyte_studio.py --no-browser --port 8123
```

Use `python3` on Linux or WSL. Once the launcher prints its address, open [http://127.0.0.1:8123/](http://127.0.0.1:8123/) in the browser on the same computer. If a previously opened tab reports a connection error, check that the launcher terminal is still running and that the address matches the printed port. Select **16-million-state benchmark** from the mode menu.

| Mode | What it runs |
| --- | --- |
| Classical | SharkVM, with a 50,000,000-instruction limit |
| Quantum | CPU statevector simulation for circuits with 1–6 qubits, including the recovery presets |
| Bounded Hybrid | Experimental quantum circuits with classical feedback and limited adaptive updates, using 2–6 qubits |
| Frontier30 (sparse) | Fixed quantum circuits with registers up to 40 qubits. Select a support cap from 4,096 to 131,072 active states. |
| Million-state benchmark | Bundled 40-qubit scaling case with a compact 1,048,576-state result |
| 16-million-state benchmark | Fixed 40-qubit, 56-gate run in a background worker; checks available RAM first, reports progress and process peak memory, and supports cancellation |

Choose **Load example** or paste source, then select **Run**. Studio shows output, metrics, the source used for the run, and SharkVM bytecode when available. The sparse mode previews large probability tables and **Save receipt** downloads the full JSON directly from the local server. Frontier30 returns probabilities. Standard Quantum mode can also report sampled counts. The [30-qubit GHZ example](examples/ghz_phase_30.sb) fits the default sparse cap, and the bundled Frontier30 example selects 131,072 automatically.

Verify downloads with `python -m sharkbyte_alpha verify-run FILE.json` (`python3` on Linux). Hash verification checks record integrity. Replay and reference comparisons address reproducibility and numerical correctness separately.

The 16-million-state Studio mode is a fixed bundled workload. It does not send its amplitude table to the browser. Before launch, Studio requires at least **4.25 GiB available physical memory** and limits the worker to **3.25 GiB**; it enforces a 90-second timeout and lets you cancel the worker. A completed run can be downloaded as a compact receipt with the source and expanded gate identity, measured elapsed time and worker memory, environment, implementation hashes, numerical checks, and references to the already archived independent Cirq checks. Verify it with `python -B tools/verify_studio_scaling_receipt.py FILE.json`. The receipt verifier checks integrity and recorded claims; hashes alone do not establish authorship.

Try `rx 1.5707963267948966 0;`, `ry -.5 0;`, or `rz .25 0;` inside a
Quantum or Frontier30 circuit. Bounded Hybrid also accepts a bound angle such as
`ry theta 0;`. Reproduce the local analytical checks with
`python -B tools/rotation_gate_evidence.py`.
[Grammar](GRAMMAR.md) · [Local rotation evidence](evidence/rotation_gate_local.json)

### Five-qubit phase-flip recovery

Choose **Quantum → Load phase-flip recovery → Run**. The [circuit](examples/phase_flip_recovery.sb) encodes a logical superposition with relative phase +π/3, extracts two parity bits, and applies coherent correction before the final measurement. Outcome strings start with the ancillas `q4 q3`, followed by the decoded data bits.

| Case | Syndrome | Expected probability of decoded data `000` |
| --- | --- | ---: |
| No error, recovery on | `00` | 100% |
| Single Z on q0, q1, or q2, recovery on | `01`, `11`, or `10` | 100% |
| Single Z on q0, q1, or q2, recovery off | `01`, `11`, or `10` | 0% |
| Z on q1, input phase −π/3, check fixed at +π/3 | `11` | 25% |
| Two Z errors, recovery on | `10` for q0+q1, `11` for q0+q2, `01` for q1+q2 | 25% |

**Load two-error control** injects Z on q1 and q2. Its syndrome matches a single error on q0, so the decoder flips q0 and leaves a logical X. The wrong-phase and two-error controls each returned `000` in 247 of 1,024 shots, consistent with 25% overlap for this input. The recovery cases returned `000` in all 1,024 shots each. The results describe ideal simulated gates, this logical input, and the specified injected errors.

[All eleven receipts and their exact circuits](evidence/phase_flip_recovery_cases.json) · Reproduce with `python -B tools/phase_flip_recovery_cases.py`.

Studio also includes an interactive **Phase-flip noise sweep**. It shows the exact expected decoded-`000` probability under an independent per-data-qubit Z channel, comparing one unencoded qubit with the three-qubit code and ideal recovery. For this logical input, zero or one error is corrected exactly; two or more errors leave a 25% decoded-`000` overlap. Thus the curves are `1 − 0.75p` (unencoded) and `1 − 0.75(3p² − 2p³)` (encoded). This is an analytical channel model, not gate-by-gate noise, noisy readout, finite-shot sampling, or a claim about hardware.

## Sparse simulation benchmarks

Active states are the basis states tracked at once. Register width and active state count measure different things. A dense array for 40 qubits would occupy 16 TiB at 16 bytes per complex amplitude. The production simulator uses sparse storage and runs on a CPU; the adaptive candidate below is an experimental 20-qubit comparison and does not change the default backend.

### Experimental sparse scaling to 1,048,576 active states

In Studio, choose **Million-state benchmark → Run**. The runner appends the three Hadamards listed in the receipt to the source shown in the editor. The recorded browser-launched run reached **1,048,576 active states in 3.020 s** of sparse evolution on Windows ARM64. [Browser receipt](benchmarks/sb_quantum_benchmark/million-state-browser-receipt.json)

The terminal measurements use this same 40-qubit circuit family, with additional Hadamards to grow its support. Times cover sparse evolution. Windows peak working set was observed by polling the runner process.

| Active states | Gates | Windows ARM64 evolution | Runner peak |
| ---: | ---: | ---: | ---: |
| 131,072 | 49 | 0.210 s | 46.5 MiB |
| 262,144 | 50 | 0.647 s | 70.6 MiB |
| 524,288 | 51 | 0.906 s | 110.4 MiB |
| 1,048,576 | 52 | 2.033 s | 195.8 MiB |
| 2,097,152 | 53 | 2.768 s | 369 MiB |
| 4,194,304 | 54 | 5.988 s | 723 MiB |
| 8,388,608 | 55 | 11.095 s | 1.39 GiB |

[2-million run data](benchmarks/sb_quantum_benchmark/scaling-2097152.json) · [4-million run data](benchmarks/sb_quantum_benchmark/scaling-4194304.json) · [8-million run data](benchmarks/sb_quantum_benchmark/scaling-8388608.json)

### Scaling to 16,777,216 active states

The terminal runner completed the **40-qubit, 56-gate** experiment on both platforms. Each run checked state count, probability normalization, and agreement with the expected uniform probabilities.

The new Studio worker was also launched through the local Studio `/run` endpoint on Windows ARM64. It reached **16,777,216 active states**, passed its exact count and probability checks, and produced a compact downloadable receipt. Sparse evolution took **16.338 s**, total worker time including startup and validation was **22.016 s**, and the Windows Job Object recorded **2.77 GiB peak process memory**. The probability sum was `0.999999999999996`; the maximum uniform-probability error was `2.65e-22`. [Studio receipt](evidence/studio_16m/windows_arm64/sharkbyte-studio-154ec294e514455890da424efe9b9361.json) · [Evidence manifest](evidence/studio_16m/windows_arm64/manifest.json)

| Environment | Python | Sparse evolution | Runner process memory | Evidence |
| --- | --- | ---: | ---: | --- |
| Windows ARM64 | 3.12.10 | 17.614 s | 2.77 GiB peak working set | [Windows JSON](benchmarks/sb_quantum_benchmark/scaling-16777216.json) |
| Ubuntu ARM64 under WSL2 | 3.14.4 | 15.639 s | 2.78 GiB peak RSS | [Ubuntu JSON](benchmarks/sb_quantum_benchmark/scaling-16777216-ubuntu-wsl.json) |

The Ubuntu process ran with a 3.06 GiB address-space limit. These are single local measurements and use different OS memory counters. The terminal runner prints a compact summary. Studio now also offers this fixed 16-million-state case as a resource-bounded background run; it does not materialize the full probability table in the browser.

```text
python -B benchmarks/sb_quantum_benchmark/support_scaling.py 16777216
```

#### Independent Cirq comparison

A separate Ubuntu ARM64 WSL2 run checked **all 16,777,216 complex amplitudes**
against Google Cirq 1.6.1. The 56-gate circuit separates into eight groups
with at most seven qubits each. Cirq simulated each group in double precision,
and the checker multiplied their amplitudes for every populated SharkByte
basis state. The reference support count matched SharkByte's, and the maximum
complex amplitude error was **6.36e-19**. This result relies on the circuit's
disconnected groups. [Cirq receipt](benchmarks/sb_quantum_benchmark/scaling-16777216-cirq.json)

Run from the repository root using the
[Cirq validation environment](INDEPENDENT_QUANTUM_VALIDATION.md#google-cirq-cross-check-on-ubuntu):

```sh
"$CIRQ_ENV/bin/python" -B tools/run_cirq_scaling_check.py --output cirq-scaling-receipt.json
```

#### Cross-platform evidence

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Verification.ipynb)

Select a CPU runtime and choose **Run all** to reproduce the checks and download the receipts.

| Environment | Qiskit and Cirq reference suite | 16,777,216 active states |
| --- | --- | --- |
| Windows ARM64 | Native Qiskit 2.6.2 and Cirq 1.7.0 both passed 120/120 using the same host. Qiskit and rustworkx were built locally from pinned source. | Cirq matched every populated amplitude |
| Ubuntu WSL2 ARM64 | Both references passed 120 seeded circuits | Cirq matched every populated amplitude |
| GitHub Actions Ubuntu | Both references passed 120 seeded circuits | Large run is separate from CI |
| Google Colab Linux x86_64 | Both references passed 120 seeded circuits | Cirq matched every populated amplitude |

On native Windows ARM64, Cirq 1.7.0 also matched all 16,777,216 populated
amplitudes with a maximum complex amplitude error of `6.36e-19`.
[Windows ARM64 Cirq scaling receipt](evidence/windows-arm64-cirq/cirq-16777216.json) · [Native Qiskit and Cirq suite receipts](evidence/windows-arm64-qiskit/)

Colab compared 3,196 amplitudes in the seeded suite with a maximum error of
`5.93e-16` against each engine. The 40-qubit circuit's maximum complex amplitude
error was `7.40e-19`. SharkByte evolution took 36.025 s and the amplitude comparison
took 8.901 s. The Colab receipts are tied to source revision `bfad672`.
[Colab receipts and SHA-256 index](evidence/colab-bfad672/)

### Connected-circuit verification

The earlier 120-circuit reference suite and 16,777,216-state disconnected
benchmark are described above. New isolated-branch work adds 24 connected
circuits compared with independent Qiskit and Cirq statevectors through 16
qubits, plus exact sparse/analytic connected GHZ checks at 20, 24, 30, and 40
qubits. A connected-but-separable control confirms that a connected gate graph
alone does not prove entanglement. The 20–40-qubit checks use a closed-form GHZ
oracle; they are not dense general-circuit simulations.

The new suite, compiler edge-case fix, exact commands, limits, performance
measurements, source hashes, and receipts are documented in the
[connected-circuit audit](docs/connected-circuit-frontier.md). The packaged
receipts and state vectors are indexed by its [SHA-256 manifest](evidence/connected-circuit-frontier/MANIFEST.json).

### Experimental adaptive sparse/dense comparison

This experimental driver runs the same connected 20-qubit circuits through the original sparse engine, a dense NumPy candidate, and an adaptive sparse/dense candidate. Each backend ran in its own process, with one warmup and seven timed repetitions. The table reports median state evolution time and process-lifetime peak RSS. All three cases passed full componentwise comparison against the dense candidate, exact support checks, and normalization checks. The 1,048,576-state connected circuit also reuses the already archived complete Qiskit and Cirq comparisons for this exact source and gate sequence; those reference runs were not repeated here.

| Host | Circuit | Exact support | Sparse median / RSS | Dense median / RSS | Adaptive median / RSS |
| --- | --- | ---: | ---: | ---: | ---: |
| Windows ARM64 | Connected GHZ | 2 | 0.000039 s / 67.7 MiB | 0.211745 s / 101.1 MiB | 0.000114 s / 67.6 MiB |
| Windows ARM64 | Intermediate support | 1,024 | 0.002583 s / 67.9 MiB | 0.376259 s / 101.2 MiB | 0.007553 s / 68.0 MiB |
| Windows ARM64 | Random connected | 1,048,576 | 22.070 s / 439.0 MiB | 0.629 s / 118.7 MiB | 0.480 s / 110.6 MiB |
| Ubuntu WSL2 ARM64 | Connected GHZ | 2 | 0.000038 s / 53.3 MiB | 0.117005 s / 104.0 MiB | 0.000108 s / 53.3 MiB |
| Ubuntu WSL2 ARM64 | Intermediate support | 1,024 | 0.001712 s / 93.3 MiB | 0.154134 s / 102.0 MiB | 0.003983 s / 93.3 MiB |
| Ubuntu WSL2 ARM64 | Random connected | 1,048,576 | 15.508 s / 481.7 MiB | 0.239 s / 126.0 MiB | 0.236 s / 115.0 MiB |

The adaptive candidate switched once from sparse to dense on the random connected case, before a Hadamard expanded support from 65,536 to 131,072 states. Its complete vector matched the dense candidate exactly in both environments. It was substantially faster than the sparse dictionary on this high-support workload, faster than dense on Windows, and effectively tied with dense on WSL2; the small WSL2 timing difference is not treated as a demonstrated speedup. Sparse remains faster for the low-support cases, where adaptive bookkeeping adds overhead. The candidate therefore remains experimental and is not enabled by default. No amplitudes were pruned, and dense simulation was limited to 20 qubits.

[Combined evidence index](evidence/adaptive_sparse_dense/manifest.json) · [Windows ARM64 report](evidence/adaptive_sparse_dense/windows_arm64/adaptive-sparse-dense-windows-arm64.json) · [Windows manifest](evidence/adaptive_sparse_dense/windows_arm64/manifest.json) · [Ubuntu WSL2 ARM64 report](evidence/adaptive_sparse_dense/ubuntu_wsl2/adaptive-sparse-dense-ubuntu-wsl2-aarch64.json) · [Ubuntu manifest](evidence/adaptive_sparse_dense/ubuntu_wsl2/manifest.json) · [Run the comparison](tools/high_support/benchmark_adaptive.py) · [Adaptive implementation](tools/high_support/adaptive_statevector.py)

## Terminal quickstart

From the checkout, run `python -B sharkbyte_terminal.py` (`python3` on Linux). Try `/help`, `/bell`, `/bell-phase`, or `/qft`. The QFT example embeds a six-qubit transform in a 30-qubit register. Use `/run FILE.sb` for a custom quantum circuit, or `/run-frontier FILE.sb` for a sparse circuit at the default cap.

Save a result with `/save result.json`, check it with `/verify result.json`, and rerun compatible circuit receipts with `/replay result.json`. Quote paths with spaces. Floating-point results can vary across platforms.

### Enable local NPU chat on Windows ARM64

For optional chat, install [Qualcomm GenieX](https://geniex.aihub.qualcomm.com/en/get-started/what-is-geniex) and run from the checkout:

```powershell
geniex --skip-update pull qualcomm/Qwen3-0.6B:W4A16 --model-hub aihub
.\Open-SharkByte-AI.ps1 -Terminal
```

The launcher uses Qualcomm's precompiled model weights and connects via loopback. Check live GenieX runtime status to confirm the device used for inference. The circuit and VM commands run independently on the CPU. For custom paths, see the [launcher parameters](Open-SharkByte-AI.ps1).

## Install

Use CPython 3.10+ and pip. The CLI has no external runtime dependencies. Studio runs from the source checkout.

```text
python -m pip install .
sharkbyte doctor
sharkbyte run examples/example.sb --backend vm
sharkbyte run examples/bell.sb --mode quantum
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm
sharkbyte qasm examples/bell.sb --output bell.qasm
sharkbyte verify-run examples/drawdown_risk_demo_overflow_guard.receipt.json
```

The OpenQASM 3 exporter covers the documented circuit subset. See [installation and offline builds](INSTALL.md), [language grammar](GRAMMAR.md), and [calculation limits](docs/CALCULATION_CAPABILITIES.md). The [research examples](docs/RESEARCH_GAP_CALCULATIONS.md) include finite calculations in the language. The [drawdown example](examples/drawdown_risk_demo.sb) is a fixed-point VM demonstration.

## Reproduce the public benchmarks

- [Frontier30 reference suite](benchmarks/sb_quantum_benchmark/) checks analytical amplitudes under a 4,096-state cap and verifies refusal when a gate would exceed it. [GitHub Actions](.github/workflows/ci.yml) runs this suite. The 16-million-state measurements above came from local runs.
- The same Windows and Ubuntu CI matrix runs the [eleven phase-flip recovery cases](tools/phase_flip_recovery_cases.py) and uploads each platform's JSON receipts as a workflow artifact. The committed [reference receipts](evidence/phase_flip_recovery_cases.json) remain directly reproducible from the command above.
- [Backend agreement](benchmarks/backend_agreement/README.md) compares SharkVM, the native interpreter, and Direct AArch64 on Linux ARM64. [The recorded reference check](https://github.com/reggaesharkk/SharkByte/commit/0beed08fc99235d8de1f594448dfa7fc80a46c08) passed 27 cases. Native execution remains disabled in the public CLI and Studio.
- [Live Qiskit and Cirq validation](INDEPENDENT_QUANTUM_VALIDATION.md) compares 120 seeded circuits across SharkByte's dense and sparse CPU simulators and two independent reference engines. GitHub Actions uploads the reports.
- [High-support connected-circuit verification](docs/high-support-connected-entanglement.md) compares seeded 17-, 18-, and 20-qubit full statevectors with Qiskit and Cirq, checks entanglement by Schmidt spectra, and records the connected separable control and cancellation limitation.
- [Qiskit reference provenance](QISKIT_PROVENANCE.md) describes the archived comparisons for 22 circuits and 320 probabilities. Run `python tools/replay_qiskit_vectors.py` to compare those archived reference values.
- [Acceptance scope](PUBLIC_STAGE_ACCEPTANCE.md) · [Claim boundaries](CLAIM_BOUNDARIES.md) · [System map](ECOSYSTEM_MAP.md) · [Reggae Shark Universe](https://github.com/reggaesharkk/Reggae-shark-universe-)

## Cite SharkByte

| Cite | Zenodo DOI |
| --- | --- |
| SharkByte across all versions | [10.5281/zenodo.24213558](https://doi.org/10.5281/zenodo.24213558) |
| Studio source snapshot with the million-state browser receipt | [10.5281/zenodo.24246003](https://doi.org/10.5281/zenodo.24246003) |
| Original standalone alpha 0.2.1a2 | [10.5281/zenodo.24213559](https://doi.org/10.5281/zenodo.24213559) |

The Studio archive freezes commit [18e4eae](https://github.com/reggaesharkk/SharkByte/commit/18e4eae2463eef9c768f15c0818963337456d9a6). For the later phase-flip controls and 16-million-state runs, cite the applicable GitHub revision and evidence file. Current first-party source and the Studio archive use [Apache 2.0](LICENSE). The earlier Zenodo alpha remains MIT. See [license history](LICENSE_STATUS.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
