# Independent quantum validation with Qiskit and Cirq

The suite compares SharkByte's dense CPU simulator and the Frontier30
source loader and sparse simulator with Qiskit Statevector. A separate pass
constructs the same circuits in Google Cirq and compares its complex
amplitudes with both Qiskit and dense SharkByte.

## Reproducible setup

Keep the verification environment and receipts outside the source checkout.
The commands below use a fresh date-stamped result folder, so prior host
receipts remain untouched.

### Native Windows ARM64 Qiskit

Native CPython 3.12.10 passed the live suite using locally built ARM64
wheels for Qiskit 2.6.2 and rustworkx 0.18.1. The pinned upstream archives
are checked by SHA-256. The build used ARM64 MSVC 14.34.31933, Windows SDK
10.0.22621.0, and Rust 1.100.0. Regenerating the rustworkx lockfile pruned
ten unused crate entries. The remaining crate identities and checksums
matched the original lockfile. Qiskit's lockfile stayed byte-identical.

Use an ARM64 Rust bin directory and an MSVC root that contains
`bin/Hostarm64/arm64`. From the repository root in PowerShell:

```powershell
$results = Join-Path $env:TEMP ("sharkbyte-qiskit-" + [guid]::NewGuid())
.\tools\build_windows_arm64_qiskit.ps1 -Output $results -RustBin $rustBin -MsvcRoot $msvcRoot
$qiskitPython = "$results/.venv/Scripts/python.exe"
& $qiskitPython -B tools/verify_windows_arm64_qiskit_wheels.py "$results/wheelhouse"
& $qiskitPython -m pip install --only-binary=:all: --find-links "$results/wheelhouse" -r requirements-independent-quantum.txt
& $qiskitPython -m pip check
& $qiskitPython -B tools/run_independent_quantum_validation.py --output "$results/qiskit.json"
& $qiskitPython -B -m unittest validation.independent_qiskit.test_suite -v
```

[Native live Qiskit, Cirq, and wheel receipts](evidence/windows-arm64-qiskit/)
record the result and the ARM64 PE machine type of both extension modules.

### Native Windows ARM64 Cirq

The verified Windows run used ARM64 CPython 3.12 and Cirq 1.7.0. Use a
fresh environment and results directory, then run these commands from
the repository root:

```powershell
$results = Join-Path $env:TEMP ("sharkbyte-cirq-" + [guid]::NewGuid())
New-Item -ItemType Directory $results | Out-Null
python -m venv "$results/.venv"
$cirqPython = "$results/.venv/Scripts/python.exe"
& $cirqPython -m pip install --only-binary=:all: cirq-core==1.7.0
& $cirqPython -m pip check
& $cirqPython -B tools/run_cirq_crosscheck.py evidence/colab-bfad672/qiskit.json --output "$results/cirq-120.json"
& $cirqPython -B tools/run_cirq_scaling_check.py --output "$results/cirq-16777216.json"
```

The small suite compares native Cirq against the archived Colab Qiskit
and SharkByte vectors. The scaling check runs SharkByte and Cirq locally.
To compare with a fresh native Qiskit run, pass its `qiskit.json` instead of
the archived Colab path. Ubuntu WSL2 is also supported below.

### Ubuntu WSL2

    RESULTS=/mnt/d/boss/results/independent-quantum-validation_2026-11-15/ubuntu-wsl2
    mkdir -p "$RESULTS"
    QISKIT_ENV=$(mktemp -d "$HOME/sharkbyte-qiskit.XXXXXXXX")
    python3 -m venv "$QISKIT_ENV"
    "$QISKIT_ENV/bin/python" -m pip install -r /mnt/d/boss/SharkByte/requirements-independent-quantum.txt
    "$QISKIT_ENV/bin/python" -B /mnt/d/boss/SharkByte/tools/run_independent_quantum_validation.py --output "$RESULTS/receipt.json"
    cd /mnt/d/boss/SharkByte
    "$QISKIT_ENV/bin/python" -B -m unittest validation.independent_qiskit.test_suite -v
    "$QISKIT_ENV/bin/python" -B -m unittest discover -s tests -v

The new virtual environments are per-run. The runner refuses to overwrite an
existing receipt. requirements-independent-quantum.txt pins Qiskit and its
direct runtime dependencies; the receipt records all installed distributions.

### Google Cirq cross-check on Ubuntu

From the repository root, point the Cirq runner at a passing Qiskit receipt
generated from the same circuit corpus. Keep the virtual environment on the
Linux filesystem for WSL, and write the receipt to the results directory.

    CIRQ_ENV=$(mktemp -d "$HOME/sharkbyte-cirq.XXXXXXXX")
    python3 -m venv "$CIRQ_ENV"
    "$CIRQ_ENV/bin/python" -m pip install cirq-core==1.6.1
    "$CIRQ_ENV/bin/python" -m pip check
    "$CIRQ_ENV/bin/python" -B tools/run_cirq_crosscheck.py "$RESULTS/receipt.json" --output "$RESULTS/cirq-crosscheck.json"

The Cirq receipt records the reference receipt hash, Cirq and NumPy versions,
revision, and per-circuit amplitude and normalization errors. The hosted
workflow runs the Cirq comparison after live Qiskit in a separate environment.

## Method

- 120 independently seeded circuits use seeds 2026111500 through 2026111619.
  Each has 1–6 qubits, all eight supported gates (H, X, Z, CX, CP, RX, RY,
  RZ), and randomized order and additional gates. Each exact SharkByte source
  string is SHA-256 hashed and parsed before execution.
- Qiskit instructions and register width come from the seeded generator's
  canonical inputs. The test separately checks the parsed SharkByte sequence
  and Qiskit's actual instruction names, qubit indices, parameters, and order
  against that shared canonical input.
- Complex statevectors are aligned by their overlap phase before amplitude
  comparison. The suite also compares each basis probability, L1 probability
  error, and norm. Statevector array indices use qubit 0 as the least-significant
  bit; explicit single-qubit and controlled-gate tests verify this convention.
- The same circuits run through Frontier30's source loader and the dense
  simulator. The receipt preserves complete probability and complex amplitude
  vectors per random circuit, all seeds, source hashes, package versions, host
  data, tolerances, gate lists, numerical errors, and status.
- Focused cases cover inverses for all eight gates, Hadamard and phase
  interference, all ordered two-qubit CP control/target pairs, angle boundaries
  including ±4π, rejected just-out-of-range and nonfinite values, and a
  synthetic global-phase alignment check. Three additional tests require the
  harness to reject an incorrect width, sparse RY sign, and dense RX coefficient.

Default acceptance limits are 1e-10 for phase-aligned maximum amplitude error,
1e-10 for maximum probability error, 1e-9 for L1 probability error, and 1e-10
for normalization error. The sparse/dense limits are recorded separately in
the receipt.

## CI scope

The separate workflow runs only for pull requests touching the simulator,
sparse quantum benchmark, validator, pinned requirements, or its own workflow.
It is additive; the existing SharkByte CI workflow remains unchanged. A manual
workflow dispatch is also available.
