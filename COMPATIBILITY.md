# Compatibility — standalone alpha 0.2.1a2

Earlier host acceptance reported Windows ARM64 and Ubuntu aarch64 installation/execution for this candidate line; these are historical reports, not fresh results from this public checkout. The included GitHub Actions workflow runs on hosted Ubuntu and Windows x86-64 runners, not ARM64.

The Qiskit comparison uses Qiskit 2.6.2 on Ubuntu aarch64 for 22 circuits. The archived CLI and quantum source fixtures match the stated 0.2.2a1 hashes; no whole-package identity is claimed. Both native backends are disabled. Historical 8097 `.sbh` compatibility is outside this acceptance scope.

The local Studio additionally has a fixed experimental 40-qubit, 56-gate sparse benchmark. Its Windows ARM64 Studio-launched run is recorded in `evidence/studio_16m/windows_arm64/`; the receipt binds the exact source and gate sequence, and cites historical Cirq checks for that same disconnected circuit. The worker does not invoke Qiskit or Cirq. Linux Studio refusal, cancellation, and receipt paths are covered by tests; a Linux Studio-launched 16-million-state run is not part of this change.

The adaptive sparse/dense implementation is a separate experimental 20-qubit candidate. Three opt-in CLI outcomes were independently replayed on Windows ARM64 and Ubuntu WSL2 ARM64 from this checkout: GHZ20 completion, connected random20 sparse-to-dense switching, and a 1 MiB resource refusal. Those receipts and replay reports are under `evidence/adaptive-cli-cross-platform-20261118/`. The separate candidate comparison uses a dense NumPy reference on both platforms and reuses archived Qiskit and Cirq comparisons for the connected high-support case. GitHub-hosted Ubuntu and Windows x86-64 test jobs replay these records; a separate Ubuntu ARM64 job checks backend agreement only. The candidate is not the default simulator, and the results do not establish dense suitability for 40-qubit registers.


The new web/app compiler uses Python standard-library APIs and generates static web files. Its platform acceptance is pending the current branch's Windows and Ubuntu CI runs; no browser automation or cross-browser compatibility claim is made.
