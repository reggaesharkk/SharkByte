# SharkByte standalone alpha 0.2.1a2

A separately curated, source-only public snapshot of a bounded experimental language toolchain. It includes an installable Python CLI, SharkVM, classical statevector simulator, bounded hybrid orchestration, examples, tests, and a scoped independent Qiskit reference fixture set.

**Start with `main` for current SharkByte source and benchmarks.** Current first-party source is licensed under [Apache License 2.0](LICENSE), SPDX identifier `Apache-2.0`. Earlier revisions already released under MIT remain available under their original terms; see [License and branch history](LICENSE_STATUS.md). Third-party tools retain their own terms.

**Cite SharkByte standalone alpha 0.2.1a2** using the Zenodo version DOI. That immutable archive preserves source commit `f5c537a76fe2f1cab12288fa29f6820cf453eb40`, which carries the MIT grant. Current GitHub `main` uses Apache-2.0; a later `main` change does not alter the Zenodo archive. Choose the license that matches the exact version you download. [DOI 10.5281/zenodo.24213559](https://doi.org/10.5281/zenodo.24213559)

**Choose a starting point.** [Terminal and optional local chat](#terminal-quickstart) · [Desktop chat](#sharkbyte-chat) · [Benchmarks](#reproduce-the-public-benchmarks) · [Install the CLI](#install) · [System map and evidence boundaries](ECOSYSTEM_MAP.md)

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

## SharkByte Chat

I built a local chat window that runs SharkByte examples and your own `.sb` programs. On Windows, double-click [Open-SharkByte-Chat.cmd](Open-SharkByte-Chat.cmd). You can also run `python -B sharkbyte_chat.py` from this checkout with Python and Tk installed.

Click **Run Bell**, **Run Frontier30**, or **Explain Bell** to start. You can also type `Run Classical` or `Run Hybrid`. Open a source file or paste an `sb` code block, then press **Enter** to send. Use **Shift+Enter** for a new line. For a custom sparse run, put `run frontier cap 8192` on the line before the code block. Use **Save result** to export the full result and source.

For general conversation, start a local model and pass its chat completions URL and served model ID with `--endpoint` and `--model`. The URL must be on the local loopback interface. Model replies appear as text. The app runs SharkByte through its built-in commands.

The installed CLI supports SharkVM and refuses native execution. Quantum circuits run in a classical simulator. SharkVM is not a security sandbox.

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
sharkbyte qasm examples/bell.sb --output bell.qasm
sharkbyte verify-run result.json
```

`examples/drawdown_risk_demo.sb` calculates an illustrative drawdown multiplier in SharkByte's own integer VM. It prints, in order: the fixed-point ratio, the multiplier in parts per million, and an example quantity in millionths. For the bundled input, the outputs are `500000`, `462117`, and `2310585`. The saved receipt can be checked with the command above. The example uses a documented Padé approximation for `tanh`; it is a language demonstration, not a trading signal or order system. Receipt hashes are unkeyed integrity checks, not proof of authorship or correctness.

Run python tools/ci_acceptance.py for isolated install and regressions. python tools/replay_qiskit_vectors.py compares archived reference values; it does not invoke Qiskit.

See [PUBLIC_STAGE_ACCEPTANCE.md](PUBLIC_STAGE_ACCEPTANCE.md) for the Windows ARM64 acceptance record and the scope of this current revision's hosted CI run.

The frozen archive and wheel are excluded because their immutable nested evidence contains personal-data disclosures; this tree is not byte-identical to them. This project is licensed under Apache License 2.0; see LICENSE and NOTICE. Public visibility is not a license grant beyond those terms. Gate 1 containment and cancellation remain unresolved; native execution stays disabled.
