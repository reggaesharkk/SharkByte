# High-support connected-circuit evidence

## Provenance

- Experiment branch: `codex/high-support-connected-entanglement`
- Current commit: `a2b59ec83b5a00dbca11b5548ac1f5982289ce2b`
- Parent experiment implementation: `e2ce913900433aecacc9c7e2ab069915bee965d2`
- Final receipt runner SHA-256: `6e0e4fef92cb7ceda83f9b8f6f356166fe04dcff53ee0a27f2e80e7d3e57156c`
- The [manifest](final_current/manifest.json) inventories 96 source, plan, receipt, comparison, and local result files by byte count and SHA-256. It identifies unkeyed digests; hashes do not establish authorship or scientific correctness.

The committed folders contain every backend receipt, comparison report, the profile summary, and raw `cProfile` database. Complete `.npy` state vectors are preserved locally at `D:\boss\results\sharkbyte-high-support-entanglement\final_current` and their hashes are included in the manifest. They are not stored in Git because the full set is hundreds of megabytes. The comparison receipts are small; the test commands below regenerate the vectors.

## Status

- `random_connected` at 17, 18, and 20 qubits: **PASS** on complete Qiskit, Cirq, dense NumPy, and SharkByte sparse statevector comparisons.
- `connected_separable` at 20 qubits: **PASS** negative control. Its interaction graph is connected and support is full, but the balanced-cut Schmidt rank is 1 and purity is 1.
- `numerical_adversary` at 17 qubits: **PASS** across all four statevector implementations; angles approach the documented 4π limit.
- `roundtrip` at 17 and 18 qubits: **PASS** for recovery of the zero state within amplitude tolerance. Exact support compaction after cancellation is **OPEN** because floating residuals are kept without pruning.
- Windows ARM64: Qiskit 2.6.2 and Cirq 1.7.0 independently executed the same source.
- Ubuntu ARM64 / WSL2: Qiskit 2.6.2, dense NumPy, and sparse SharkByte executed the 20-qubit case and matched the full Windows Cirq vector. Cirq-in-WSL is **NOT TESTED**; it is not installed in that environment.
- Quantum hardware, circuits above 20 qubits, and an optimized production sparse backend: **NOT TESTED**.

## Reproduction

From a clean checkout with Python 3.12 and the pinned references:

```powershell
python -m pip install -r requirements-high-support.txt
python -B -m unittest validation.high_support.test_high_support -v
python -B tools/high_support/run_suite.py --case random_connected --width 20 --output-dir results/random20 --repeat 3
```

The runner generates and compares all four backends in one environment. The checked-in source and deterministic plan are verified before execution. The 17- and 18-qubit cases use the same command with the corresponding `--width` and a new output directory.

## Existing PR review

PR #7 was reviewed separately and left unchanged and unmerged. Its base remains main at `db140939c4ed96447f3d614653c128e5a41df2f3`; its latest observed workflow run #73 passed all five jobs. This experiment branch was created from main rather than from PR #7, so it neither repeats nor modifies PR #7's changes. No release was created.
