# SharkByte standalone alpha 0.2.1a2 — scoped specification

The `sharkbyte` CLI supports `--version`, `doctor`, classical `run FILE --backend vm`, `run FILE --mode quantum`, bounded `run FILE --mode hybrid --backend vm`, `qasm FILE --output FILE.qasm`, and `verify-run FILE.json`.

The record stores exact UTF-8 source, source SHA-256, mode, and result. Classical receipts also include bytecode and its digest. SHA-256 fields are unkeyed integrity checks; they do not prove authorship or correctness.

Documented implementation bounds: classical source at most 65,536 UTF-8 bytes and classical VM at most 50,000,000 instructions; quantum 1–6 qubits, at most 256 gates, 1–100,000 shots, and finite bounded controlled-phase angles; hybrid 2–6 qubits, up to 100,000 VM instructions, bounded shots and 1–8 iterations. Quantum execution is classical CPU statevector simulation.

QASM emits OpenQASM 3 declarations, supported gates in source order, and `c[i] = measure q[i]`. Qubit 0 is the least-significant state-index bit; displayed bitstrings are MSB-left. The Qiskit reference subset covers 22 circuits only; this is not a general OpenQASM conformance claim.

Both native backends refuse execution with `native backends are disabled: containment unavailable`. No native execution, containment, or cancellation claim is made.
