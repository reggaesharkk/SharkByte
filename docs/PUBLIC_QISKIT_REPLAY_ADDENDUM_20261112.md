# Public source Qiskit replay — dated addendum

**Evidence date:** 2026-11-11 UTC; review/addendum date: 2026-11-12
**Source:** public `reggaesharkk/SharkByte` commit `95f936aa32e10ee8ef726093889067086e4c4421`
**Host reported:** Ubuntu aarch64, CPython 3.14.4
**External tools:** Qiskit 2.6.2, OpenQASM3 1.0.1, qiskit-qasm3-import 0.6.0

This addendum supplements, but does not rewrite, earlier acceptance reports that said this direct replay was not executed. The host evidence is identified as `ubuntu_qiskit_20261111T221339Z`; its four entries were independently read and checked against the saved SHA-256 manifest in the local closure review. The host-local evidence path is intentionally omitted from this public-facing document.

## Result

The saved replay JSON and stdout report **22/22 fixtures**, **320 basis-state probability entries**, and no fixture errors. Maximum public-versus-Qiskit per-state probability difference was `4.440892098500626e-16`; maximum L1 difference was `5.273559366969494e-16`; maximum normalization error was `1.9984014443252818e-15`. These are below the replay's declared per-state `1e-9`, L1 `1e-8`, and normalization `1e-10` limits. Qiskit also matched each archived independent vector with maximum recorded archived-vector L1 difference 0.0. QASM was parsed/imported and executed as Qiskit statevectors for all recorded circuits.

The source provenance check identifies the public commit exactly and verifies the scoped `sharkbyte_alpha/cli.py` and `sharkbyte_alpha/quantum.py` SHA-256 values. The reference vectors originate from separate 0.2.2a1 quantum evidence. This does **not** establish whole-package identity between 0.2.1a2 and 0.2.2a1.

The recorded convention is statevector integer index q0 least-significant bit, display bitstrings MSB-left, and QASM `c[i] = measure q[i]`. Results are for a classical statevector simulator only; no quantum hardware was used.

## Diagnostic caveat

The preserved `replay.stderr.txt` contains a NumPy `ComplexWarning`. The original auxiliary norm calculation used `float(complex_inner_product).real`; the complex-to-float cast is unnecessary and generates the warning. This did not alter the probability comparisons. The distribution gate is complete for the stated 22 fixtures; a warning-free rerun of the auxiliary norm diagnostic was not performed, and this addendum makes no warning-free norm-diagnostic claim. The original run and its hashes remain immutable. A corrected diagnostic script is retained in the local review workspace, not substituted into historical host evidence.

## Scope and release effect

Distribution agreement gate: **PASS, scoped to these 22 fixtures / 320 probabilities**. Statevector-norm diagnostic: **CAVEAT retained; warning-free rerun not performed and not required for the distribution comparison**. The result does not establish universal OpenQASM conformance, mathematical proof, physical quantum execution, native execution, native process containment, or Gate 1 closure.
