# Integrated Google Colab verification

The CPU runtime tested SharkByte revision `ec876e2c51844068e01d8fac2ee86b83983514a9` on Linux x86_64. All 17 recorded checks passed.

- [Full 40-qubit Cirq receipt](cirq-40q-16777216.json) records 16,777,216 populated amplitudes checked over eight disconnected components. The maximum complex amplitude error was 7.4032e-19.
- [24-case Qiskit/Cirq comparison](connected-comparison.json) records agreement for the connected corpus.
- [20-qubit comparison](random_connected-20/random_connected_20q_comparison.json) records the largest connected case in this run. The [separable control](connected_separable-20/connected_separable_20q_comparison.json) uses the same register width and full support.
- [Run summary and original inventory](colab-summary.json) record the environment, commands, statuses, and hashes for all 54 payload files. This directory preserves the original JSON bytes. The original ZIP also contains logs and two statevector archives, which are recorded in the inventory.

Original ZIP SHA-256: `ec7209df16f24262a816cf55f543c2b22d3eb534904f31731679fa6fd45b8a00`.

[Run the pinned notebook in Colab](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Integrated-Verification.ipynb).
