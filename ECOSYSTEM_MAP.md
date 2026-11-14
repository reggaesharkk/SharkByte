# How the SharkByte pieces fit together

I built SharkByte as a programming-language and verification project. The chat window is one way to use it; it is not the language runtime, and the model is not the simulator.

## The public repository

| Piece | Where it lives | What it does | What it does not prove |
| --- | --- | --- | --- |
| SharkByte language and CLI | `GRAMMAR.md`, `SPEC.md`, `sharkbyte_alpha/`, `sharkbyte_guarded_entry.py` | Parses and runs the documented classical, quantum, and experimental hybrid subsets with explicit limits and receipts. | Native host execution is disabled. A SHA-256 receipt checks integrity, not authorship or mathematical correctness. |
| Desktop and terminal chat | `sharkbyte_chat.py`, `sharkbyte_terminal.py` | Offers a simple interface for examples and `.sb` programs. | The chat UI is not a new compiler or a general-purpose trained model. |
| Optional natural-language model | `Open-SharkByte-AI.ps1`, `sharkbyte_local_http.py` | Connects ordinary chat text to a separately installed local model service. The launcher requests Qualcomm GenieX and its NPU execution mode on supported Windows ARM64 systems. | A model name, launcher setting, `/doctor` line, or downloaded weights alone do not prove that an answer used the NPU. Confirm a live inference and device status in GenieX. The repository does not include custom-trained weights. |
| Small statevector simulator | `sharkbyte_alpha/quantum.py` | Computes the supported small quantum circuits on the CPU and can sample from the resulting state. | It is software simulation, not a physical quantum processor. |
| Frontier30 sparse experiment | `benchmarks/sb_quantum_benchmark/` | Runs selected sparse `.sb` circuits on a classical CPU. The checked-in benchmark has a 4,096-populated-state limit and checks amplitudes against analytical references. | “30 qubits” describes register width, not a dense simulation of all 2³⁰ states. The separate larger-cap experiments are not part of the checked-in 4,096-state receipt. |
| Backend-agreement evidence | `benchmarks/backend_agreement/` | Preserves a scoped set of legacy VM, native-interpreter, and direct-native comparisons. | These results are tied to their stated source revision and environment; they do not enable native execution in the installed CLI or establish host isolation. |
| Independent quantum reference fixtures | `evidence/qiskit_0.2.2a1/`, `QISKIT_PROVENANCE.md` | Stores a bounded comparison set with provenance and replayable expected probabilities. | It is not a claim of full Qiskit or OpenQASM conformance. |
| Fixed-point risk calculation example | `examples/drawdown_risk_demo.sb` | Recreates one illustrative IntentSeal drawdown calculation in SharkByte's integer VM using a documented fixed-point approximation. | It is a language example only; it is not a signal, a calibrated risk policy, or a broker integration. |

## What happens when I use the chat

1. A normal-language prompt goes to the optional local model service, when that service is running.
2. A built-in command such as `/bell`, `/qft`, or `/run FILE.sb` goes to SharkByte's deterministic software tools.
3. The simulator result is displayed as simulator output. The model can help explain it, but a model explanation is not itself a verification result.
4. A saved receipt records the source and result. `/verify` checks the stored hashes; `/replay` reruns the source. The Frontier30 benchmark separately compares selected amplitudes with analytical values.

## Keep the wider research ecosystem connected by interfaces

The author's other SharkByte-named checkouts, SharkLang, Protocol, Interceptor, Witness, local research assistant, model-training experiments, and umbrella repository are related projects, but they are not all modules of this public package. Some have different versions, evidence status, or licenses. I keep them separate until a specific interface is mapped, the behavior is reconciled, and the source rights are checked.

The intended connections are narrow: SharkByte supplies deterministic program execution and receipts; the local assistant may supply cited project context; language and protocol projects may supply separately versioned policy or verification adapters. This repository currently does not claim that those separate systems are bundled, trained into one model, or all connected at runtime. The risk example translates one formula from the separately prepared IntentSeal trading starter into SharkByte fixed-point integer operations so we can exercise our own language; it does not connect SharkByte to the trading scripts.

## Reproduce the public sparse benchmark

From the repository root, run:

```sh
python -B benchmarks/sb_quantum_benchmark/sb_end_to_end_bench.py --output benchmarks/sb_quantum_benchmark/results.json
```

It prints a JSON receipt and writes the same receipt to the named file. The receipt records circuit and module hashes, analytical amplitude errors, timing, memory, and the expected refusal when `branch13.sb` would exceed the 4,096-state cap. Timing and memory values are machine-specific. This benchmark runs on the CPU; it does not measure NPU inference.
