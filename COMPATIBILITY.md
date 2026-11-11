# Compatibility — standalone alpha 0.2.1a2

Earlier host acceptance reported Windows ARM64 and Ubuntu aarch64 installation/execution for this candidate line; these are historical reports, not fresh results from this public checkout. The included GitHub Actions workflow runs on hosted Ubuntu and Windows x86-64 runners, not ARM64.

The Qiskit comparison uses Qiskit 2.6.2 on Ubuntu aarch64 for 22 circuits. Current `cli.py` and `quantum.py` match the stated 0.2.2a1 hashes; no whole-package identity is claimed. Both native backends are disabled. Historical 8097 `.sbh` compatibility is outside this acceptance scope.
