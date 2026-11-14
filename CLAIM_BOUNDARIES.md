# Claim boundaries — 0.2.1a2 public source snapshot

Claims are limited to the documented CLI, VM, classical statevector simulator, bounded hybrid subset, and checked-in examples/tests. The Qiskit comparison covers 22 circuits and 320 probabilities. It is separately sourced from 0.2.2a1: `cli.py` and `quantum.py` match by SHA-256, while whole-package identity is not claimed.

- Quantum results are classical simulation, not hardware results.
- OpenQASM behavior is checked for a finite subset, not all of OpenQASM 3.
- Sampled counts may vary across PRNG/runtime versions.
- Native interpreter and direct AArch64 execution remain disabled.
- Native process containment and cancellation (Gate 1) remain unresolved.
- SharkVM is not a security sandbox.
- The working grammar is not normative or complete.
- This is not a general-purpose production compiler.
- The current public source tree is licensed under Apache License 2.0 (SPDX identifier `Apache-2.0`); see [LICENSE](LICENSE), [NOTICE](NOTICE), and [License and branch history](LICENSE_STATUS.md). This applies to first-party material in this tree. Earlier MIT-licensed revisions retain their original grant, archived revisions keep the license file distributed with them, and external tools retain their own terms.
