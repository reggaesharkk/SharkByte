# Claim boundaries — 0.2.1a2 public source snapshot

Claims are limited to the documented CLI, VM, classical statevector simulator, bounded hybrid subset, and checked-in examples/tests. The Qiskit comparison covers 22 circuits and 320 probabilities. It is separately sourced from 0.2.2a1: the archived CLI and quantum source fixtures match by SHA-256, while whole-package identity is not claimed.

- Quantum results are classical simulation, not hardware results.
- The 16,777,216-state Studio mode is one fixed CPU sparse benchmark. Its receipt verifies the analytical count and probability checks and links historical Cirq checks for the exact same circuit; the Studio worker does not run Cirq or independently recompute every amplitude.
- Adaptive sparse/dense results cover three 20-qubit workloads. Complete candidate vectors matched the dense NumPy candidate; the connected high-support circuit additionally reuses pre-existing Qiskit and Cirq receipts. Sparse remains faster for the tested low-support circuits, and the adaptive candidate is not enabled by default.
- No dense 40-qubit statevector was allocated or tested.
- OpenQASM behavior is checked for a finite subset, not all of OpenQASM 3.
- Sampled counts may vary across PRNG/runtime versions.
- Native interpreter and direct AArch64 execution remain disabled.
- Native process containment and cancellation (Gate 1) remain unresolved.
- SharkVM is not a security sandbox.
- The working grammar is not normative or complete.
- This is not a general-purpose production compiler.
- The current public source tree is licensed under Apache License 2.0 (SPDX identifier `Apache-2.0`); see [LICENSE](LICENSE), [NOTICE](NOTICE), and [License and branch history](LICENSE_STATUS.md). This applies to first-party material in this tree. Earlier MIT-licensed revisions retain their original grant, archived revisions keep the license file distributed with them, and external tools retain their own terms.

- The connected reference corpus, the high-support Schmidt comparisons, and the 40-qubit sparse scaling benchmark establish different results. The scaling circuit has eight disconnected components. The connected GHZ checks through 40 qubits use a closed-form oracle.
- The WP19 replay bounds arithmetic rounding for assumed rates and defect. Its mathematical assumptions and PDE bounds remain open.
