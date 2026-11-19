# SharkByte

**A programming language, bounded execution toolchain, and reproducible computational research workspace.**

Write classical programs in `.sb`, describe quantum circuits for **CPU simulation**, combine them with bounded classical feedback, build static websites and browser apps, and explore a separately integrated numerical-dynamics laboratory. SharkByte is an experimental, inspectable alpha: implementations, limitations, tests, and source-bound evidence are part of the project—not an afterthought.

[![SharkByte CI](https://github.com/reggaesharkk/SharkByte/actions/workflows/ci.yml/badge.svg)](https://github.com/reggaesharkk/SharkByte/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](pyproject.toml)
[![Status: experimental alpha](https://img.shields.io/badge/status-experimental%20alpha-6f42c1.svg)](CLAIM_BOUNDARIES.md)

**[Quick start](#quick-start)** · **[Language examples](#write-sharkbyte)** · **[Studio](#three-workspaces-one-local-studio)** · **[Evidence](#independent-verification-and-benchmarks)** · **[Documentation](#documentation-map)** · **[Research boundaries](#what-sharkbyte-does-not-claim)**

## Verified achievements — Google Cloud, Colab, and local systems

**SharkByte's public results span local Windows ARM64, Ubuntu ARM64 under WSL2, Google Colab CPUs, and Google Compute Engine.** These are measured, source-linked experiments with distinct verification methods—not a single claim that every workload is supported by the same execution engine.

| Where it ran | Verified milestone | Evidence |
| --- | --- | --- |
| **Google Compute Engine (Linux x86_64)** | **4,294,967,296 packed GHZ-family basis/amplitude entries checked** against a closed-form parity reference. The two array SHA-256 digests matched the independent Colab replay; the temporary packed arrays totaled **96 GiB**. | [GCE 2³² receipt](evidence/connected-ghz50-gcp/2p32/sharkbyte-ghz50-4b-gcp-receipt.json) |
| **Google Colab (Linux x86_64)** | Independently completed the same **4,294,967,296-entry** structured materialization and full-array check. A separate connected **40-qubit / 33,554,432-populated-amplitude** sparse experiment matched its closed-form oracle. | [50-qubit Colab receipt](evidence/connected-ghz50-colab/retry-2p32/sharkbyte-connected-ghz50-4294967296-colab.json) · [40-qubit Colab receipt](evidence/connected-ghz40-32m-colab/sharkbyte-connected-ghz40-33554432-colab.json) |
| **Windows ARM64 (local Studio)** | The fixed **40-qubit / 16,777,216-state** CPU benchmark ran from Studio, recording **2.77 GiB** peak process memory. The unified release also passed **87 local tests** and **17 installed-package acceptance checks**. | [Windows Studio receipt](evidence/studio_16m/windows_arm64/sharkbyte-85c74d14dcb54040a295e3c2fe422e53.json) · [Release integration PR](https://github.com/reggaesharkk/SharkByte/pull/13) |
| **Ubuntu ARM64 under WSL2 (local)** | The same 16-million-state sparse benchmark and independent quantum reference checks were exercised in the documented ARM64 environment. This is **WSL2**, not an independent physical Ubuntu host. | [Ubuntu scaling receipt](benchmarks/sb_quantum_benchmark/scaling-16777216-ubuntu-wsl.json) · [Qiskit/Cirq methods](INDEPENDENT_QUANTUM_VALIDATION.md) |
| **Hosted GitHub Actions (Windows and Ubuntu)** | The merged unified codebase passed [SharkByte CI](https://github.com/reggaesharkk/SharkByte/actions/runs/44484290586), with separate [independent quantum validation](https://github.com/reggaesharkk/SharkByte/actions/runs/44401252706) on the integration head. | [Workflow sources](.github/workflows/) |

**One-click Google Colab notebooks** — open a notebook, select a **CPU runtime**, then choose **Runtime → Run all**.

| Notebook | Verified experiment / scope | Launch |
| --- | --- | --- |
| Integrated verification | 16,777,216-state comparison and scoped checks | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Integrated-Verification.ipynb) |
| Connected 40-qubit | 33,554,432-state sparse GHZ-family experiment | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Connected-40Q-32M.ipynb) |
| Connected 50-qubit | GHZ-family disk materialization, **up to 4,294,967,296 entries** | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Connected-50Q-2B.ipynb) |

**Run requirements:** larger experiments need substantial RAM, disk space, and execution time; a notebook may select a smaller tier or refuse a run. Integrated verification pins a historical revision, not today's `main`.

**Scope:** The 4.29-billion-entry result is **formula-based, disk-backed GHZ-family verification**, not general 50-qubit statevector simulation. Cirq checked a separate 512-shot invariant, not the entire array. The 16-million-state experiment is a separate disconnected CPU sparse workload. [Methods](tools/run_connected_ghz50_materialization.py) · [Full claim boundaries](CLAIM_BOUNDARIES.md).

---

![SharkByte Studio and a 40-qubit sparse CPU benchmark](docs/sharkbyte-studio-banner.svg)

> **What makes SharkByte distinctive:** a compact language/VM and bounded quantum simulation environment connected to independently checkable execution records, explicit resource refusals, reference-engine comparisons, and research-specific experiments. The public implementation is **not** a production compiler, quantum computer, or security sandbox.

## Explore the project

| Component | What you can do | Implementation and limits |
| --- | --- | --- |
| **Classical SharkByte** | Run integer arithmetic, variables, functions, arrays, conditions, and loops in a small language | `.sb` source compiled to SharkVM bytecode; source and instruction limits |
| **Quantum simulation** | Specify gates, seed measurements, inspect probabilities, and export supported OpenQASM 3 | Classical CPU statevector simulator; standard mode supports **1–6 qubits** |
| **Bounded Hybrid** | Run small quantum circuits with classical feedback and parameter updates | Experimental **2–6-qubit**, **1–8-iteration** subset |
| **Frontier sparse mode** | Explore supported circuits with wide registers and bounded populated state support | CPU sparse representation; a wider register does **not** imply dense simulation |
| **Adaptive quantum CLI** | Opt into sparse-to-dense switching with an explicit memory planning budget | Separate experimental backend, up to **20 qubits** for dense conversion; not the default |
| **Web / App Builder** | Author and export static websites and installable browser PWAs | Separate declarative `sharkbyte.web/v1` JSON format, not arbitrary `.sb`-to-web compilation |
| **Lucid Dynamics** | Integrate and visualize a four-state bounded-existence ODE | Optional NumPy/SciPy numerical model with pinned mathematical provenance; not a dreaming model |
| **Studio, terminal, and receipts** | Edit, run, view results, export project ZIPs and verify execution records | Local browser and CLI interfaces, with bounded and differently scoped execution paths |

Read the [working language grammar](GRAMMAR.md), [scoped specification](SPEC.md), [system architecture map](ECOSYSTEM_MAP.md), and [claim boundaries](CLAIM_BOUNDARIES.md) before extending any result beyond its documented workload.

## Quick start

**Requirements:** CPython **3.10+**, Git (for cloning), and pip. The ordinary CLI has **no external runtime dependencies**. Studio's Lucid Dynamics mode requires the optional `lucid` extra.

```sh
git clone https://github.com/reggaesharkk/SharkByte.git
cd SharkByte
python -m pip install .
sharkbyte doctor
sharkbyte run examples/example.sb --backend vm
sharkbyte run examples/bell.sb --mode quantum
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm
```

The first classical example prints `42` inside a source-bound JSON execution record. The Bell example produces simulated probabilities and seeded counts; it does not use quantum hardware.

**Launch the unified local Studio** from a source checkout:

```sh
python -m pip install -e ".[lucid]"
python -B sharkbyte_studio.py
```

Open the **local address printed by the server**, normally `http://127.0.0.1:8120/`. On Linux/WSL use `python3` if `python` is unavailable; add `--no-browser` if you want to open the URL yourself. If port 8120 is occupied, use `--port 8135` and open the printed URL. Stop the server with **Ctrl+C**.

The `lucid` extra is optional. Without it, the standard language, Quantum/VM, and Web/App tools do not need NumPy or SciPy. See [installation and isolated checks](INSTALL.md).

## Write SharkByte

SharkByte source files use the `.sb` extension. The grammar below illustrates the **implemented, bounded subset**; it is not a promise of Python/C/JavaScript compatibility.

### 1. Classical language and SharkVM

```sharkbyte
let answer = 40 + 2;
print answer;
```

Save as `hello.sb`, then run:

```sh
sharkbyte run hello.sb --backend vm --output hello-receipt.json
sharkbyte verify-run hello-receipt.json
```

The bundled equivalent is [`examples/example.sb`](examples/example.sb). For more than arithmetic, try the [fixed-point gradient-descent example](examples/research/gradient_descent_linear_fit.sb) or [research calculations](docs/RESEARCH_GAP_CALCULATIONS.md). These are finite integer computations, not machine-learning training or mathematical proofs.

### 2. Quantum circuit syntax

```sharkbyte
quantum bell {
    qubits 2;
    shots 1024;
    seed 42;
    h 0;
    cx 0 1;
    measure_all;
}
```

This is the exact syntax of the bundled [`examples/bell.sb`](examples/bell.sb). Run it with:

```sh
sharkbyte run examples/bell.sb --mode quantum --output bell-receipt.json
sharkbyte qasm examples/bell.sb --output bell.qasm
```

The supported subset includes `h`, `x`, `z`, `cx`, `cp`, and bounded-angle `rx`, `ry`, `rz` operations. The simulator is classical, and the OpenQASM 3 exporter covers only the [documented subset](SPEC.md). Qubit `q0` is the least-significant state-index bit; displayed bitstrings are MSB-left.

### 3. Classical feedback with bounded hybrid programs

The [`hybrid` example](examples/adaptive.sb) has `prepare`, `quantum`, `feedback`, and `update` blocks. It runs a fixed, small number of iterations with a bounded parameter such as `theta`.

```sh
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm --output hybrid-receipt.json
```

Hybrid programs combine a classical VM with a classical quantum **simulation**, not a physical hybrid processor.

### 4. Experimental adaptive sparse/dense CLI

```sh
python -m sharkbyte_alpha run examples/high_support/adaptive_sparse_ghz_20q.sbq --mode quantum --backend auto --memory-mib 256 --output auto-run.json
python -m sharkbyte_alpha verify-run auto-run.json
```

The opt-in `auto` backend starts sparse, evaluates a bounded dense conversion for supported cases, and records representation changes or an explicit `RESOURCE_STOP` refusal. The memory budget estimates state working memory, not total operating-system process memory. The ordinary CLI backend remains unchanged. [Adaptive evaluation and cross-platform receipts](evidence/adaptive-cli-cross-platform-20261118/).

## Three workspaces, one local Studio

Studio brings three distinct workflows together **without pretending they share the same execution engine**.

| Workspace | In Studio | What is actually executed |
| --- | --- | --- |
| **Quantum / VM** | Load `.sb` examples, run, inspect output, metrics, bytecode, and receipts | SharkVM, bounded CPU quantum simulation, hybrid subsets, and separately guarded sparse benchmark workers |
| **Web / App** | Edit a project definition, build, preview, export ZIP | A restricted JSON-to-static-HTML/CSS/JavaScript compiler; isolated local preview |
| **Lucid Dynamics** | Choose a model regime, adjust bounded parameters, inspect trajectories and phase portraits, download receipts | A separate SciPy solver for the pinned dimensionless four-state ODE |

**Quantum / VM:** the main page offers Classical, Quantum, Bounded Hybrid, Frontier30, and fixed million-state and 16-million-state demonstration modes. The latter are **specific benchmark workloads** with memory checks and resource limits, not arbitrary large-circuit guarantees. [Calculation capabilities](docs/CALCULATION_CAPABILITIES.md).

### Web / App Builder

SharkByte's Web/App feature uses a deliberately separate, typed-by-schema project representation: `sharkbyte.web/v1`. The compiler accepts selected content, navigation, chart, control, and task-form components and emits **static files**. PWA output includes a manifest and service worker; it is not a native Android/iOS app or a hosted backend.

```sh
sharkbyte web new my-website
sharkbyte web build my-website
sharkbyte web serve my-website

sharkbyte app new my-tasks
sharkbyte app build my-tasks
sharkbyte app serve my-tasks
```

Explore the [research portfolio](examples/web/research-portfolio/sharkbyte.web.json), [interactive dashboard](examples/web/interactive-dashboard/sharkbyte.web.json), and [browser-local task PWA](examples/web/task-app/sharkbyte.web.json). Studio can preview on a separate loopback origin and export a ZIP. See [the compiler specification, examples, and security scope](docs/web-app-builder.md).

### Lucid Dynamics — bounded numerical research

The opt-in **`/lucid`** page integrates the dimensionless four-state soft-wall ODE from [Theory of Bounded Existence](https://github.com/reggaesharkk/theory-of-bounded-existence), pinned to revision `5bc839e6e0cf492882268d8ed47bef6ff82d65fc`. It retains the source equations and model constants and uses a bounded LSODA integration.

| Reference regime | Model behavior at the tested initial condition | Approximate late crossing period |
| --- | --- | ---: |
| Memoryless feedback | Decay toward the near-zero state | No repeated late crossings |
| IVc — pure Ψ memory | Finite-time relaxation-cycle observation | **17.936755** |
| IVb — coupled memory | Finite-time relaxation-cycle observation | **19.387103** |

The [nine-receipt Windows ARM64 audit](docs/lucid-dynamics-audit.md) verified all canonical record digests and independently compared the original equations with a tighter Radau integration. Nine files covered **five distinct configurations**; six used overridden parameters, now labeled separately from their starting presets.

**Interpretation:** Ψ is a mathematical state variable. Numerical crossing periods do not prove a global periodic attractor or establish real lucid dreaming, consciousness, biological processes, or cosmology. Read the [ODE, solver bounds, and reproducibility guide](docs/lucid-dynamics.md).

## Independent verification and benchmarks

SharkByte treats **record integrity**, **numerical agreement**, **runtime performance**, and **mathematical proof** as different questions. Check each result at its actual commit, host, solver, workload, and resource limit.

### Current integrated release checks

The unified Studio integration was merged through [PR #13](https://github.com/reggaesharkk/SharkByte/pull/13) into `main` at commit [`df7731a0`](https://github.com/reggaesharkk/SharkByte/commit/df7731a0fb69d455ad9c050268854ce8777b0ae8).

| Check | Recorded outcome |
| --- | --- |
| Full local Windows ARM64 regression run | **87/87 tests passed** on the integrated source |
| Public installed-package acceptance | **17/17 checks passed** in the recorded Windows ARM64 release check |
| Merged `main` GitHub Actions | [SharkByte CI passed on the actual merge commit](https://github.com/reggaesharkk/SharkByte/actions/runs/44484290586) |
| Independent quantum validation of integration | [Passed on the validated integration head](https://github.com/reggaesharkk/SharkByte/actions/runs/44401252706) |
| Unified Studio browser acceptance | Local Windows ARM64 tests exercised the three workspaces, Web/App export, and Lucid page |

**Re-run the current source tree**:

```sh
python -m unittest discover -s tests -v
python tools/ci_acceptance.py
```

The acceptance harness installs the core package outside the checkout, runs normal/`-O`/`-OO` regression checks, and confirms that unsupported native execution is **refused**. The reported native refusal exit code is expected, not an executable native backend. [CI workflow](.github/workflows/ci.yml) · [Release gates](RELEASE_GATE_MATRIX.md).

### Experimental evidence and reproducibility

| Experiment | Recorded result | What it does **not** show | Read the evidence |
| --- | --- | --- | --- |
| **120 seeded quantum circuits** | Scoped comparisons with Qiskit and Cirq reference engines | Universal quantum correctness or hardware execution | [Independent validation](INDEPENDENT_QUANTUM_VALIDATION.md) |
| **20-qubit connected, high-support circuit** | 1,048,576 amplitudes compared across four methods; measured balanced-cut Schmidt rank **1,024** | A general efficient large-qubit simulation method | [Methods and receipts](docs/high-support-connected-entanglement.md) |
| **40-qubit / 16,777,216-state sparse workload** | CPU run and exact independent amplitude comparison for the specified **disconnected** circuit | A dense 40-qubit statevector or globally entangled 40-qubit experiment | [Studio receipt](evidence/studio_16m/windows_arm64/sharkbyte-85c74d14dcb54040a295e3c2fe422e53.json) · [Cirq comparison](evidence/windows-arm64-cirq/cirq-16777216.json) |
| **40-qubit / 33,554,432-state connected GHZ-family workload** | Populated sparse amplitudes matched a closed-form oracle; connected GHZ entanglement has a separate analytical justification | General dense 40-qubit evolution or a full Cirq amplitude replay of this larger state | [Receipt and manifest](evidence/connected-ghz40-32m-colab/) |
| **50-qubit / 4,294,967,296-entry GHZ-family materialization** | Disk-backed packed basis/amplitude arrays exhaustively checked against independent parity calculations; Colab and Google Compute Engine array digests matched | Structured analytical workload; see [scope above](#verified-achievements--google-cloud-colab-and-local-systems) | [Colab receipt](evidence/connected-ghz50-colab/retry-2p32/sharkbyte-connected-ghz50-4294967296-colab.json) · [Compute Engine replay](evidence/connected-ghz50-gcp/2p32/sharkbyte-ghz50-4b-gcp-receipt.json) |
| **Adaptive sparse/dense comparisons** | Repeated CPU benchmarks for three specified 20-qubit cases; full vectors matched the dense candidate | Universal speedup; low-support cases favor sparse storage | [Reports and methodology](evidence/adaptive_sparse_dense/manifest.json) |
| **Lucid Dynamics** | IVc/IVb periods reproduced; memoryless reference decayed; all nine receipts verified | Global stability, formal existence proof, or physiological interpretation | [Nine-receipt audit](docs/lucid-dynamics-audit.md) |

The earlier 2³² `RESOURCE_STOP` attempt is preserved alongside the later successful run in [historical evidence](evidence/connected-ghz50-colab/). The [materialization worker](tools/run_connected_ghz50_materialization.py) and [notebook](notebooks/SharkByte-Colab-Connected-50Q-2B.ipynb) document the exact method.

For the 40-qubit 16-million-state case, the Windows Studio worker recorded approximately **2.77 GiB** peak process memory, while a separate Linux/WSL and Colab reference program compared the populated amplitudes under its documented circuit decomposition. Times are **workload-, hardware-, and environment-specific**, not a generic benchmark against other languages.

**Open numerical issue:** sparse round-trip cancellation can leave tiny floating-point residuals represented as nonzero entries. Exact support compaction remains an open engineering limitation. [Recorded round-trip control](evidence/colab-q8w4bj57/roundtrip-17/roundtrip_17q_comparison.json).

### Reproduce and inspect evidence

```sh
# Hash-check a source-bound CLI receipt
sharkbyte verify-run examples/drawdown_risk_demo_overflow_guard.receipt.json

# Replay archived reference vectors for the documented subset
python -B tools/replay_qiskit_vectors.py --output qiskit-replay.json

# Verify a released 50-qubit structured-materialization receipt
python -B tools/verify_connected_ghz50_receipt.py evidence/connected-ghz50-gcp/2p32/sharkbyte-ghz50-4b-gcp-receipt.json

# Reproduce the small phase-flip recovery controls
python -B tools/phase_flip_recovery_cases.py

# Replay archived adaptive policy receipts
python -B tools/verify_adaptive_cli_acceptance.py --receipt-dir evidence/adaptive-cli-cross-platform-20261118/windows-arm64 --output adaptive-replay.json
```

Complete reproducibility instructions and environment-specific comparisons are in [REPRODUCIBILITY.md](REPRODUCIBILITY.md), [INDEPENDENT_QUANTUM_VALIDATION.md](INDEPENDENT_QUANTUM_VALIDATION.md), and the checked-in [evidence tree](evidence/).

**Receipt integrity is not authentication.** SHA-256 verifies the file's canonical contents against its recorded digest; it does not prove the author, the source of the run, independent correctness, or the truth of external scientific assumptions.

## Architecture and implementation boundaries

```text
                        SHARKBYTE
                           |
              +------------+-------------+
              |                          |
      .sb language / CLI             Local Studio
              |                          |
       compiler + SharkVM          +------+-------+
              |                    |      |       |
        classical integer        VM/CPU  Web/App  /lucid
          execution             simulator  DSL    SciPy ODE
              |                    |      |       |
              +----- receipts -----+   static   numerical
                   + hashes             output    receipts
```

**Designed constraints:** explicit source-size, instruction, qubit, shot, iteration, and state-support bounds; guarded resource refusals; separate web preview origin; optional scientific dependencies. These controls improve auditability and reduce accidental overreach, but **do not create an operating-system sandbox**.

The optional Windows ARM64 [GenieX local-chat launcher](Open-SharkByte-AI.ps1) is an interface to separately obtained model weights. The language runtime, VM, and simulation are **not** a trained language model, and the presence of the launcher does not demonstrate NPU inference. [Architecture and scope](ECOSYSTEM_MAP.md).

## What SharkByte does not claim

- **Not quantum hardware.** All quantum experiments here are classical CPU simulation or analytical materialization.
- **Not a production compiler or unrestricted language implementation.** The [grammar](GRAMMAR.md) and [specification](SPEC.md) document an intentionally bounded alpha subset.
- **Not a security sandbox.** Native interpreter and Direct AArch64 execution are **disabled** until containment/cancellation requirements are met. Do not execute untrusted inputs in sensitive environments. [Security policy](SECURITY.md).
- **Not a general web backend or native mobile builder.** The Web/App feature compiles the documented declarative JSON schema into static sites and browser PWAs.
- **Not a proof of human lucid dreaming or a global dynamical theorem.** Lucid Dynamics integrates a dimensionless model over tested finite horizons.
- **Not a cryptographically authenticated provenance system.** Hash checks verify integrity; independent replay, code comparison, and trusted signing are separate concerns.

See [CLAIM_BOUNDARIES.md](CLAIM_BOUNDARIES.md) for the complete claim inventory. Research examples describe finite, explicit calculations—not solutions to the Riemann hypothesis, Navier–Stokes regularity, or other open problems.

## Documentation map

| Start here | For |
| --- | --- |
| [GRAMMAR.md](GRAMMAR.md) · [SPEC.md](SPEC.md) | `.sb` syntax, semantics, and supported subsets |
| [INSTALL.md](INSTALL.md) · [COMPATIBILITY.md](COMPATIBILITY.md) | Install, execution environments, known compatibility |
| [ECOSYSTEM_MAP.md](ECOSYSTEM_MAP.md) | How the VM, simulators, web compiler, Studio, and optional chat relate |
| [docs/web-app-builder.md](docs/web-app-builder.md) | Web/App project DSL, PWA scope, and preview/export |
| [docs/lucid-dynamics.md](docs/lucid-dynamics.md) · [Lucid audit](docs/lucid-dynamics-audit.md) | Model equations, parameter ranges, solvers, numerical evidence |
| [docs/high-support-connected-entanglement.md](docs/high-support-connected-entanglement.md) | Statevector comparisons and Schmidt diagnostics |
| [docs/connected-circuit-frontier.md](docs/connected-circuit-frontier.md) | Sparse and analytical connected-circuit methods |
| [INDEPENDENT_QUANTUM_VALIDATION.md](INDEPENDENT_QUANTUM_VALIDATION.md) | Qiskit/Cirq methods and host-specific evidence |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) · [Evidence](evidence/) | Receipts, integrity manifests, notebooks, exact replay scope |
| [RELEASE_GATE_MATRIX.md](RELEASE_GATE_MATRIX.md) · [SECURITY.md](SECURITY.md) | Release status, security and native-execution limitations |
| [LICENSE_STATUS.md](LICENSE_STATUS.md) · [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | License history, software notices, third-party boundaries |

## Development and verification

From a source checkout with Python 3.10+:

```sh
python -m pip install -e ".[lucid]"
python -m unittest discover -s tests -v
python tools/ci_acceptance.py
```

The complete checkout suite covers features that are not included in the installed CLI-only package. The acceptance script deliberately tests the installed distribution **outside** the source tree. Core CI runs on Windows and Ubuntu; separate workflows cover documented independent reference-engine checks and selected ARM64 environments. Review [the workflows](.github/workflows/) rather than assuming every large experiment runs in hosted CI.

When proposing new features or numerical claims, include an executable example, deterministic or seeded regression tests where possible, input bounds, evidence tied to the exact source revision, and explicit statements of what the result does **not** establish.

## Author, citation, and license

**SharkByte was created by Prince Upadhyay.** Development history, public tests, examples, and reproducibility records are available in this repository.

| Research software record | DOI |
| --- | --- |
| SharkByte — concept DOI across versions | [10.5281/zenodo.24213558](https://doi.org/10.5281/zenodo.24213558) |
| Archived Studio source snapshot and million-state browser record | [10.5281/zenodo.24246003](https://doi.org/10.5281/zenodo.24246003) |
| Original standalone alpha `0.2.1a2` | [10.5281/zenodo.24213559](https://doi.org/10.5281/zenodo.24213559) |

The current first-party repository is licensed under **[Apache License 2.0](LICENSE)**. Earlier published **MIT** revisions retain their historical grants; the Zenodo alpha record is not silently relicensed. Consult [NOTICE](NOTICE), [LICENSE_STATUS.md](LICENSE_STATUS.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The `pyproject.toml` package version remains `0.2.1a2`; the unified Studio integration did **not** create a new tagged software release.

---

**SharkByte's central proposition is testable computation:** write a bounded program, run the appropriate engine, preserve a source-bound record, and check the result against the right independent reference—without turning a successful experiment into a broader claim than the evidence supports.
