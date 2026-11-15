# SharkByte

![SharkByte Studio. A 40-qubit circuit reached 1,048,576 active states in a local CPU benchmark.](docs/sharkbyte-studio-banner.svg)

SharkByte is an experimental programming language with a local browser workspace, a Python CLI, and a CPU simulator for quantum circuits and bounded hybrid programs.

[Launch Studio](#sharkbyte-studio) · [See the benchmark](#experimental-sparse-scaling-to-1048576-active-states) · [Inspect the run receipt](benchmarks/sb_quantum_benchmark/million-state-browser-receipt.json) · [Cite SharkByte](#cite-sharkbyte)

**The laptop run.** SharkByte Studio launched a 52-gate sparse circuit on a 40-qubit register. The simulator tracked 1,048,576 active basis states at peak and completed sparse evolution in 3.020 seconds on Windows ARM64. To reproduce it, launch Studio and select **Million-state benchmark → Run**.

## Cite SharkByte

| Cite | Zenodo DOI |
| --- | --- |
| SharkByte across all versions | [10.5281/zenodo.24213558](https://doi.org/10.5281/zenodo.24213558) |
| Studio source snapshot and million-state benchmark | [10.5281/zenodo.24246003](https://doi.org/10.5281/zenodo.24246003) |
| Original standalone alpha 0.2.1a2 | [10.5281/zenodo.24213559](https://doi.org/10.5281/zenodo.24213559) |

The Studio archive pins commit [18e4eae](https://github.com/reggaesharkk/SharkByte/commit/18e4eae2463eef9c768f15c0818963337456d9a6). First-party source in this snapshot and on current `main` uses [Apache 2.0](LICENSE). The original Zenodo alpha at commit `f5c537a` remains MIT. See the [license history](LICENSE_STATUS.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

[Terminal and local chat](#terminal-quickstart) · [Calculation capabilities](docs/CALCULATION_CAPABILITIES.md) · [Research examples](docs/RESEARCH_GAP_CALCULATIONS.md) · [Install the CLI](#install) · [System map](ECOSYSTEM_MAP.md)

**Which terminal should I use?** In Windows PowerShell, use `Open-SharkByte-AI.ps1 -Terminal` for GenieX chat on a supported NPU. In Ubuntu/WSL, use the Python commands below for CPU simulation and the Linux ARM64 backend-agreement workflow. The `.sb` language and simulator commands are independent of the chat model.

## Terminal quickstart

From the repository root, run `python -B sharkbyte_terminal.py` with Python 3.10 or later. The simulator commands work directly from the checkout and require no model.

| Type at the prompt | What it does |
| --- | --- |
| `/help` | Lists commands. |
| `/bell` | Samples a Bell circuit and checks the receipt hashes. |
| `/bell-phase` | Computes measurement probabilities for two Bell states and a classical mixture. |
| `/qft` | Runs a six-qubit Fourier transform embedded in a 30-qubit register and previews its probability distribution. |
| `/doctor` | Shows the selected chat backend and SharkByte CLI settings. |
| `/run FILE.sb` | Runs a custom quantum circuit using the CPU statevector simulator. |
| `/run-frontier FILE.sb` | Runs a custom sparse circuit with a 4,096-state cap. |
| `/save FILE.json` | Exports the last completed experiment to a new file. |
| `/verify [FILE.json]` | Checks the last receipt or a saved receipt. |
| `/replay FILE.json` | Reruns the source in a saved receipt and compares the result. |
| `/quit` | Exits. |

Try `/run examples/bell.sb`, `/save bell-result.json`, then `/verify bell-result.json` and `/replay bell-result.json`. Quote paths with spaces. You can also save and replay `/bell-phase` and `/qft` results. Receipts include the circuit source, SharkByte version, and result. Sampled circuits also record their seed and shot count. Replay compares the recorded result exactly on the same SharkByte version. Floating-point results can differ across platforms. Hash verification checks integrity, replay checks reproducibility, and the separate benchmark checks numerical accuracy against a reference.

### Enable local NPU chat on Windows ARM64

Install [Qualcomm GenieX](https://geniex.aihub.qualcomm.com/en/get-started/what-is-geniex), make sure `geniex --version` works in PowerShell, then run these commands from the repository root:

```powershell
geniex --skip-update pull qualcomm/Qwen3-0.6B:W4A16 --model-hub aihub
.\Open-SharkByte-AI.ps1 -Terminal
```

The first command downloads the model. Subsequent launches use the local cache. If GenieX is outside PATH, pass `-GenieXPath` with the executable path. For a custom cache, use GenieX's `--data-dir` when downloading and pass the same directory to the launcher with `-GenieXDataDir`.

The launcher binds GenieX to `127.0.0.1` and restricts browser access to its own origin. If a server already occupies the port with a different browser origin policy, close that server and relaunch. Both chat clients use loopback addresses and reject redirects and proxies.

With the local GenieX service running, ordinary questions are sent to the configured Qualcomm Qwen3 model. The launcher requests NPU execution; a configured backend or `/doctor` line alone does not prove that a particular reply ran on the NPU. Check GenieX's live device/runtime status for that. In the terminal prompt, built-in commands such as `/bell`, `/bell-phase`, `/qft`, `/run`, `/verify`, and `/replay` run SharkByte locally on the CPU; they do not need an NPU reply. If GenieX disconnects, ordinary chat can fail while those simulator commands remain local. The launcher uses Qualcomm's precompiled weights; this repository does not contain custom-trained model weights. For independent amplitude checks of the QFT example, run the [Frontier30 benchmark suite](benchmarks/sb_quantum_benchmark/).

## Supported functionality
- Classical SharkVM execution with a 50,000,000-instruction limit.
- Classical CPU statevector simulation for the documented quantum subset.
- Bounded hybrid execution with measurement feedback and limited adaptive updates.
- OpenQASM 3 output for the documented subset.
- SHA-256 receipt integrity checking; hashes do not authenticate a record.

For runnable calculations and the precise classical, statevector, hybrid, and sparse-simulation limits, see [What SharkByte can calculate today](docs/CALCULATION_CAPABILITIES.md).

## SharkByte Studio

Run SharkByte in a browser on your own computer. Studio uses Python 3.10+ and the source checkout. Clone this repository or download and extract the GitHub source ZIP, then open a terminal in the checkout.

**Windows PowerShell**

```powershell
python -B sharkbyte_studio.py
```

**Linux or WSL**

```bash
python3 -B sharkbyte_studio.py --no-browser
```

Open [http://127.0.0.1:8120/](http://127.0.0.1:8120/) if the browser does not open automatically. Keep the terminal running while using Studio. Press Ctrl+C to stop it. If port 8120 is in use, pass `--port 8121` and use the URL printed in the terminal.

Choose Classical, Quantum, Bounded Hybrid or Frontier30 (sparse), then select **Load example** or paste your own SharkByte source. Select **Run** to inspect the output, execution metrics, bytecode when emitted, and the exact source snapshot. **Save receipt** downloads the SharkByte JSON record for local inspection or verification with `python -m sharkbyte_alpha verify-run FILE.json`.

Bounded Hybrid accepts 2–6 qubits. Frontier30 runs fixed quantum blocks with a selectable support cap (4,096 by default, or 8,192, 16,384, 32,768, 65,536, or 131,072 states) and reports probabilities. The sparse parser accepts registers up to 40 qubits. Loading the bundled 40-qubit example selects 131,072 states. The [65,536-state circuit](examples/frontier_sparse_40.sb) is also available. The separate [30-qubit GHZ example](examples/ghz_phase_30.sb) fits the default cap. Frontier30 reports probabilities. Its output does not include sampled counts.

Studio listens on loopback and runs the public SharkVM and CPU simulation modes. Its worker timing includes process startup. The Linux ARM64 three-backend workflow is documented separately in the [backend agreement benchmark](benchmarks/backend_agreement/README.md).

### Five-qubit phase-flip recovery

In Studio, choose **Quantum > Load phase-flip recovery > Run**. The [circuit](examples/phase_flip_recovery.sb) encodes a logical superposition with relative phase +pi/3, injects a single Z error, and uses two ancillas to control the correction before the final measurement. The decoded data should read `000` after reversing the state preparation. Bitstrings put syndrome bits `q4 q3` first.

| Case | Syndrome | Expected probability of decoded data `000` |
| --- | --- | ---: |
| No error, recovery on | 00 | 1 |
| Z on q0, q1, or q2, recovery on | 01, 11, or 10 | 1 |
| Z on q0, q1, or q2, recovery off | 01, 11, or 10 | 0 |
| Z on q1, recovery on, input phase -pi/3 | 11 | 0.25 |

The wrong-phase control keeps the verification phase fixed at +pi/3. The 25% overlap is the expected outcome; a test that requires perfect recovery rejects this input. These are ideal qubit simulations for this logical input and single-error model. The [eight case receipts](evidence/phase_flip_recovery_cases.json) include the complete source for each case, outcome probabilities, shot counts, and SHA-256 integrity hashes.

```text
python -B tools/phase_flip_recovery_cases.py
```

### Measured sparse simulation on Windows ARM64

| Circuit | Qubits | Gates | Peak active states | Evidence |
| --- | ---: | ---: | ---: | --- |
| [Controlled-phase circuit](examples/frontier_sparse_40.sb) | 40 | 48 | 65,536 | Studio receipt passed SHA-256 verification |
| [Extended controlled-phase circuit](examples/frontier_sparse_40_131072.sb) | 40 | 49 | 131,072 | Three local runs passed |

The 131,072-state circuit ran on a Windows ARM64 laptop with Python 3.12.10. Across three runs, sparse evolution took 0.128 to 0.131 seconds. Process wall time, including startup and probability JSON output, was 1.43 to 1.48 seconds. Windows reported approximately 97 MiB of peak working set for the standalone runner process, observed by polling. Each JSON output was about 9.37 MB. The memory figure covers the runner process only. Chrome and Studio server memory were outside that measurement.

For scale, a dense 40-qubit array with 16-byte complex amplitudes would occupy 16 TiB for the array alone. The measured circuit has 131,072 populated basis states, which is why sparse storage fits on a laptop.

Reproduce from the checkout:

```text
python -B benchmarks/sb_quantum_benchmark/frontier30.py examples/frontier_sparse_40_131072.sb --support-cap 131072
```

### Experimental sparse scaling to 1,048,576 active states

The experiment keeps the register at 40 qubits and appends one Hadamard per doubling to the 49-gate example above. Each run checked the expected active state count, probability normalization, and the analytical uniform probabilities for this circuit family.

| Active states | Gates | Evolution time | Peak runner working set |
| ---: | ---: | ---: | ---: |
| 131,072 | 49 | 0.210 s | 46.5 MiB |
| 262,144 | 50 | 0.647 s | 70.6 MiB |
| 524,288 | 51 | 0.906 s | 110.4 MiB |
| 1,048,576 | 52 | 2.033 s | 195.8 MiB |

In a separate run started from the Studio Web IDE, the 52-gate circuit reached 1,048,576 active states in 3.020 seconds of evolution. The probabilities summed to 0.9999999999999967, with a maximum absolute error of 3.60e-21 against the expected uniform distribution. The downloaded receipt passed SharkByte SHA-256 integrity verification. [Browser run receipt](benchmarks/sb_quantum_benchmark/million-state-browser-receipt.json)

One run per row on Windows ARM64 with Python 3.12.10. Evolution time excludes summary serialization and the probability checks. Windows peak working set was observed by polling the runner process. In Studio, select **Million-state benchmark** and click **Run** to reproduce a compact result and download its receipt. The runner appends the three Hadamards listed in the [published Studio receipt](benchmarks/sb_quantum_benchmark/million-state-receipt.json) to the source shown in the editor. This experiment emits a compact summary and uses an explicit sparse memory budget. Studio continues to offer full probability receipts through 131,072 states.

```text
python -B benchmarks/sb_quantum_benchmark/support_scaling.py 1048576
```

### Scaling to 16,777,216 active states

The same 40-qubit circuit family reached **16,777,216 active states** on Windows ARM64 with Python 3.12.10. All four local runs passed checks for state count, normalization, and uniform probabilities.

| Active states | Gates | Sparse evolution | Peak runner working set | Run data |
| ---: | ---: | ---: | ---: | --- |
| 2,097,152 | 53 | 2.768 s | 369 MiB | [JSON](benchmarks/sb_quantum_benchmark/scaling-2097152.json) |
| 4,194,304 | 54 | 5.988 s | 723 MiB | [JSON](benchmarks/sb_quantum_benchmark/scaling-4194304.json) |
| 8,388,608 | 55 | 11.095 s | 1.39 GiB | [JSON](benchmarks/sb_quantum_benchmark/scaling-8388608.json) |
| 16,777,216 | 56 | 17.614 s | 2.77 GiB | [JSON](benchmarks/sb_quantum_benchmark/scaling-16777216.json) |

Ubuntu ARM64 under WSL2 also completed the 16,777,216-state circuit with Python 3.14.4. Evolution took **15.639 s** and peak resident memory was **2.78 GiB** under a **3.06 GiB** process address-space limit. The state count and probability checks matched the Windows result. [Ubuntu run data](benchmarks/sb_quantum_benchmark/scaling-16777216-ubuntu-wsl.json).

One run per row. Windows process peak working set was observed by polling. Times cover sparse evolution. These runs use the terminal benchmark with compact output.

```text
python -B benchmarks/sb_quantum_benchmark/support_scaling.py 16777216
```

## Reproduce the public benchmarks

- [Backend agreement](benchmarks/backend_agreement/README.md) runs SharkVM, Direct AArch64, and the native interpreter from a source checkout on Linux ARM64 with Python, Clang, and LLD. On the [verified source revision](https://github.com/reggaesharkk/SharkByte/commit/0beed08fc99235d8de1f594448dfa7fc80a46c08), nine programs passed on each backend (27/27), and all three produced the expected diagnostic for their configured 50,000,000-instruction or tick budget. The Apache-authorized source revision also passed its Ubuntu 24.04 ARM64 backend and budget jobs in [GitHub Actions](https://github.com/reggaesharkk/SharkByte/actions/runs/43602167885). Use trusted local programs. Host isolation remains unverified.
- I built Frontier30 to run custom SharkByte `.sb` circuits with a sparse simulator on a classical CPU. The checked-in benchmark uses a 4,096-state cap, compares bundled circuits with analytical amplitudes, and confirms that `branch13.sb` is refused when it would grow support to 8,192. You can run separate experiments with larger caps, but those results are distinct from the checked-in receipt. [Run Frontier30 locally](benchmarks/sb_quantum_benchmark/) · [Windows and Ubuntu CI](https://github.com/reggaesharkk/SharkByte/actions/runs/43602167885)

The [Reggae Shark Universe](https://github.com/reggaesharkk/Reggae-shark-universe-) indexes SharkByte alongside the other public projects.

The included Qiskit fixture subset covers 22 circuits / 320 probabilities and uses separately accepted Qiskit 2.6.2 reference results with 0.2.2a1 quantum provenance. Only specified modules match this candidate; no whole-package identity is claimed. See QISKIT_PROVENANCE.md.

## Install
Requires CPython 3.10+ and pip; runtime dependencies are empty. PEP 517 build isolation is enabled, with setuptools==84.2.0 pinned in pyproject.toml.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Ubuntu/macOS:      . .venv/bin/activate
python -m pip install .
sharkbyte --version
sharkbyte doctor
```

For offline installation, download the pinned build requirements and dependencies on a connected machine, then transfer the wheelhouse:
```sh
python -m pip download --only-binary=:all: --dest build-wheelhouse -r BUILD_REQUIREMENTS.txt
python -m pip install --no-index --find-links build-wheelhouse .
```
Keep pip's normal build isolation enabled. See INSTALL.md.

## Examples
```sh
sharkbyte run examples/example.sb --backend vm
sharkbyte run examples/bell.sb --mode quantum
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm
sharkbyte run examples/drawdown_risk_demo.sb --backend vm
sharkbyte verify-run examples/drawdown_risk_demo.receipt.json
sharkbyte verify-run examples/drawdown_risk_demo_overflow_guard.receipt.json
sharkbyte qasm examples/bell.sb --output bell.qasm
sharkbyte verify-run result.json
```

`examples/drawdown_risk_demo.sb` calculates an illustrative drawdown multiplier in SharkByte's own integer VM. It prints, in order: the fixed-point ratio, the multiplier in parts per million, and an example quantity in millionths. For the bundled input, the outputs are `500000`, `462117`, and `2310585`. The original saved receipt is retained as the pre-guard record; the current source-matched receipt is `examples/drawdown_risk_demo_overflow_guard.receipt.json`. The example clamps nonpositive ratios to 0, uses a fixed-point Padé approximation for `tanh` below a ratio of 6, and saturates at 1.0 above that threshold. The threshold avoids signed 64-bit overflow, and the final result stays within `[0, 1]`. This is a language demonstration, not a trading signal or order system. Receipt hashes are unkeyed integrity checks, not proof of authorship or correctness.

Run python tools/ci_acceptance.py for isolated install and regressions. python tools/replay_qiskit_vectors.py compares archived reference values; it does not invoke Qiskit.

See [PUBLIC_STAGE_ACCEPTANCE.md](PUBLIC_STAGE_ACCEPTANCE.md) for the Windows ARM64 acceptance record and the scope of this current revision's hosted CI run.

The frozen archive and wheel are excluded because their immutable nested evidence contains personal-data disclosures; this tree is not byte-identical to them. This project is licensed under Apache License 2.0; see LICENSE and NOTICE. Public visibility is not a license grant beyond those terms. Gate 1 containment and cancellation remain unresolved; native execution stays disabled.
