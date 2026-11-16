# Compatibility — standalone alpha 0.2.1a2

Earlier host acceptance reported Windows ARM64 and Ubuntu aarch64 installation/execution for this candidate line; these are historical reports, not fresh results from this public checkout. The included GitHub Actions workflow runs on hosted Ubuntu and Windows x86-64 runners, not ARM64.

The Qiskit comparison uses Qiskit 2.6.2 on Ubuntu aarch64 for 22 circuits. The archived CLI and quantum source fixtures match the stated 0.2.2a1 hashes; no whole-package identity is claimed. Both native backends are disabled. Historical 8097 `.sbh` compatibility is outside this acceptance scope.

The local Studio additionally has a fixed experimental 40-qubit, 56-gate sparse benchmark. Its Windows ARM64 Studio-launched run is recorded in `evidence/studio_16m/windows_arm64/`; the receipt binds the exact source and gate sequence, and cites historical Cirq checks for that same disconnected circuit. The worker does not invoke Qiskit or Cirq. Linux Studio refusal, cancellation, and receipt paths are covered by tests; a Linux Studio-launched 16-million-state run is not part of this change.

The adaptive sparse/dense implementation is a separate experimental 20-qubit candidate. It is compared with the dense NumPy reference on Windows ARM64 and Ubuntu WSL2 ARM64; the connected high-support case also points to already archived Qiskit and Cirq comparisons. The candidate is not the default simulator, and the results do not establish dense suitability for 40-qubit registers.
