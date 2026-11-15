# Independent live-Qiskit quantum validation

This validation runs the same deterministic SharkByte source circuits through
SharkByte's public parser and dense CPU statevector simulator, its isolated
sparse prototype, and Qiskit's Statevector.from_instruction. It does not
change either simulator or enable native execution. Qiskit is a classical
reference simulator; this is not a hardware test or a general OpenQASM claim.

## Reproducible setup

Keep the verification environment and receipts outside the source checkout.
The commands below use a fresh date-stamped result folder, so prior host
receipts remain untouched.

### Windows PowerShell ARM64

    $results = 'D:\boss\results\independent-quantum-validation_2026-11-15\windows-arm64'
    New-Item -ItemType Directory -Force $results | Out-Null
    python -m venv "$results\.venv"
    & "$results\.venv\Scripts\python.exe" -m pip install -r 'D:\boss\SharkByte\requirements-independent-quantum.txt'
    & "$results\.venv\Scripts\python.exe" -B 'D:\boss\SharkByte\tools\run_independent_quantum_validation.py' --output "$results\receipt.json"
    Push-Location 'D:\boss\SharkByte'
    & "$results\.venv\Scripts\python.exe" -B -m unittest validation.independent_qiskit.test_suite -v
    & "$results\.venv\Scripts\python.exe" -B -m unittest discover -s tests -v
    Pop-Location

### Ubuntu WSL2

    RESULTS=/mnt/d/boss/results/independent-quantum-validation_2026-11-15/ubuntu-wsl2
    mkdir -p "$RESULTS"
    python3 -m venv "$RESULTS/.venv"
    "$RESULTS/.venv/bin/python" -m pip install -r /mnt/d/boss/SharkByte/requirements-independent-quantum.txt
    "$RESULTS/.venv/bin/python" -B /mnt/d/boss/SharkByte/tools/run_independent_quantum_validation.py --output "$RESULTS/receipt.json"
    cd /mnt/d/boss/SharkByte
    "$RESULTS/.venv/bin/python" -B -m unittest validation.independent_qiskit.test_suite -v
    "$RESULTS/.venv/bin/python" -B -m unittest discover -s tests -v

The new virtual environments are per-run. The runner refuses to overwrite an
existing receipt. requirements-independent-quantum.txt pins Qiskit 2.6.2.

## Method

- 120 independently seeded circuits use seeds 2026111500 through 2026111619.
  Each has 2–6 qubits, all eight supported gates (H, X, Z, CX, CP, RX, RY,
  RZ), and randomized order and additional gates. Each exact SharkByte source
  string is SHA-256 hashed and parsed before execution.
- Qiskit instructions are built from the seeded generator's gate list before
  SharkByte parsing. The test separately checks the parsed SharkByte sequence
  and Qiskit's actual instruction names, qubit indices, parameters, and order
  against that shared canonical input.
- Complex statevectors are aligned by their overlap phase before amplitude
  comparison. The suite also compares each basis probability, L1 probability
  error, and norm. Statevector array indices use qubit 0 as the least-significant
  bit; explicit single-qubit and controlled-gate tests verify this convention.
- The same 120 circuits run through the experimental sparse prototype and dense
  simulator. The receipt preserves complete probability and complex amplitude
  vectors per random circuit, all seeds, source hashes, package versions, host
  data, tolerances, gate lists, numerical errors, and status.
- Focused cases cover inverses for all eight gates, Hadamard and phase
  interference, all ordered two-qubit CP control/target pairs, angle boundaries
  including ±4π, rejected just-out-of-range and nonfinite values, and a
  synthetic global-phase alignment check.

Default acceptance limits are 1e-10 for phase-aligned maximum amplitude error,
1e-10 for maximum probability error, 1e-9 for L1 probability error, and 1e-10
for normalization error. The sparse/dense limits are recorded separately in
the receipt.

## CI scope

The separate workflow runs only for pull requests touching the simulator,
sparse quantum benchmark, validator, pinned requirements, or its own workflow.
It is additive; the existing SharkByte CI workflow remains unchanged. A manual
workflow dispatch is also available.
