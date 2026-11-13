# AGENTS.md — SharkByte standalone alpha 0.2.1a2

This file captures the scoped contract from `SPEC.md` so any future session can pick up work with full context. The working tree is at `d:\AI\repos\SharkByte`, branch `main`, clean at commit `95f936a` ("Publish scoped SharkByte standalone alpha source").

## Scope & status

- Package: `sharkbyte-standalone-alpha` version `0.2.1a2` (`pyproject.toml`, `sharkbyte_alpha/__init__.py`).
- CPython 3.10+, empty runtime dependencies, PEP 517 build isolation, `setuptools==84.2.0` pinned.
- CLI entry: `sharkbyte_guarded_entry:main` (console script `sharkbyte`); module entry `python -m sharkbyte_alpha`.
- **No license had been selected.** A standard MIT `LICENSE` has now been added at the repo root (this session).
- CI runs via `.github/workflows/ci.yml` on push/PR across Ubuntu and Windows (consolidated; the prior `.github/workflows/tests.yml` was removed to avoid duplicate runs). Fresh Linux/aarch64 acceptance still pending.
- Native execution, containment, and cancellation remain **disabled/unverified**; no claim is made.

## SPEC.md bounds (authoritative contract)

### CLI commands
- `sharkbyte --version` → prints `SharkByte standalone 0.2.1a2`
- `sharkbyte doctor` → JSON: version, python, architecture, vm_step_limit, native=`disabled`, hybrid=`experimental vm`
- `sharkbyte run FILE --backend vm` (classical, default mode) → record envelope incl. bytecode + bytecode_sha256
- `sharkbyte run FILE --mode quantum` → record envelope (no bytecode)
- `sharkbyte run FILE --mode hybrid --backend vm` → bounded hybrid orchestrator record
- `sharkbyte qasm FILE --output FILE.qasm` → OpenQASM 3.0; output must differ from source; fails if same path
- `sharkbyte verify-run FILE.json` → verifies record_sha256, source_sha256, bytecode_sha256 (if present); returns `INTEGRITY_VERIFIED`

### Resource bounds (enforced; violations raise ValueError)
- Classical source: ≤ 65,536 UTF-8 bytes (`read_source`).
- VM: ≤ 100,000 instructions (`VM_STEPS`).
- Quantum: 1–6 qubits (`MAX_QUBITS=6`), ≤ 256 gates (`MAX_GATES=256`), 1–100,000 shots (`MAX_SHOTS=100000`), CP angle |angle| ≤ 4π.
- Hybrid: 2–6 qubits, bounded shots, 1–8 iterations (9 iterations raises ValueError).

### Record envelope (`cli.envelope`)
```json
{
  "schema": 1,
  "toolchain_version": "0.2.1a2",
  "mode": "classical|quantum|hybrid",
  "source": "<exact UTF-8 source>",
  "source_sha256": "<sha256 of source utf-8>",
  "result": {...},
  "bytecode_hex": "...",          // classical only
  "bytecode_sha256": "...",       // classical only
  "record_sha256": "<sha256 of canonical body without record_sha256>"
}
```
`cli.verify(record)` recomputes all hashes; mismatch → ValueError. Hashes are unkeyed integrity checks only — they do not prove authorship or correctness.

### QASM output (`quantum.to_qasm`)
- Header: `OPENQASM 3.0;`, `include "stdgates.inc";`, `qubit[n] q;`, `bit[n] c;`
- Gates emitted in source order: `cx q[a], q[b];`, `cp(<angle>) q[c], q[t];`, `<op> q[i];`
- Measurements: `c[i] = measure q[i];` for each qubit
- Qubit 0 is the least-significant state-index bit; displayed bitstrings are MSB-left.
- Qiskit reference subset covers 22 circuits / 320 probabilities only — not a general OpenQASM conformance claim.

### Native backends
- Any `--backend` other than `vm` → exit 1, no stdout, stderr: `sharkbyte: ValueError: native backends are disabled: containment unavailable`
- This is a negative containment-refusal test, not native functionality.

## Source layout
- `sharkbyte_alpha/{__init__.py,cli.py,vm.py,quantum.py,hybrid.py,_vendor/*}` — implementation
- `sharkbyte_guarded_entry.py` — console entry; refuses conflicting SharkByte on PYTHONPATH (exit 2)
- `tools/ci_acceptance.py` — isolated PEP 517 install + regressions outside the source checkout; runs tests under normal/-O/-OO and CLI smokes + native guard refusals
- `tools/replay_qiskit_vectors.py` — compares archived reference probabilities; does NOT invoke Qiskit
- `tests/{test_acceptance,test_cli,test_independent_qiskit_evidence,test_release_edges,test_three_mode}.py` — 30 tests total

## Commands
- Install: `python -m pip install .` (offline: `python -m pip download --only-binary=:all: --dest build-wheelhouse -r BUILD_REQUIREMENTS.txt` then `pip install --no-index --find-links build-wheelhouse .`)
- Test: `python -m unittest discover -s tests -v` (expect 30/30 OK)
- Isolated CI: `python tools/ci_acceptance.py` (expect exit 0, status PASS)
- QASM: `sharkbyte qasm examples/bell.sb --output bell.qasm`
- Verify: `sharkbyte verify-run result.json`

## Examples
- `examples/example.sb` → classical, prints `42`, 5 VM instructions
- `examples/bell.sb` → quantum bell state
- `examples/adaptive.sb` → hybrid, 4 iterations, 2 qubits, 2048 shots
