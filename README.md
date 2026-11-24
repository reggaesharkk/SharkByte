# SharkByte

**An independent programming language, CPU simulation and numerical-verification toolchain, and reproducible research workspace.**

Write classical programs in `.sb`, simulate bounded quantum circuits on a CPU, build websites and browser apps, and investigate independently replayable numerical certificates. SharkByte's standard language/VM and core simulation do **not require NumPy or SciPy**; the separately integrated Lucid Dynamics laboratory uses an optional NumPy/SciPy extra. SharkByte remains an experimental, inspectable alpha: implementations, limitations, tests, and source-bound evidence are part of the project—not an afterthought.

[![SharkByte CI](https://github.com/reggaesharkk/SharkByte/actions/workflows/ci.yml/badge.svg)](https://github.com/reggaesharkk/SharkByte/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](pyproject.toml)
[![Status: experimental alpha](https://img.shields.io/badge/status-experimental%20alpha-6f42c1.svg)](CLAIM_BOUNDARIES.md)

**[Verified milestones](#verified-achievements--google-cloud-colab-and-local-systems)** · **[Colab notebooks](#verified-achievements--google-cloud-colab-and-local-systems)** · **[Quick start](#quick-start)** · **[Studio](#three-workspaces-one-local-studio)** · **[H3/H4 certification](#h3h4-hadamard-research-what-is-established)** · **[Evidence](#independent-verification-and-benchmarks)** · **[Research boundaries](#what-sharkbyte-does-not-claim)**

I do not treat a correct output as sufficient evidence. I ask whether its source is pinned, whether its result survives an independent replay, and where the argument stops. I am not trying to make a machine appear powerful. I am trying to understand the boundary between what can be computed, what can be verified, and what can honestly be claimed as known.

## Private research milestones — Gates 6B.15–6B.23

**SharkByte Certify RC1 is ready for scoped private developer trials.** These milestones summarize private research and deployment evidence. The proofs, original fixtures, SDK, and native verifier are held privately. The public checkout provides the language, VM, Studio, builders, notebooks, and research replays documented below.

| Milestone | Verified scope |
| --- | --- |
| **Lean 4 quantum certificate soundness** | Kernel-checked soundness for the admitted contract, with concrete byte acceptance for a one-X certificate and a mixed X/Z/CX/H certificate. |
| **Exact rational dot products** | Kernel-checked exact dot-product soundness and concrete source-bound byte acceptance for the weighted-return result **13/250**. |
| **Clean proof reproduction** | All **74 project Lean modules** rebuilt from pinned sources on ARM64 Ubuntu WSL2 and uncapped Linux x86-64 on Google Compute Engine. These were private proof rebuilds. |
| **Native verifier on Google Compute Engine** | The Linux x86-64 executable matched expected outcomes on **220/220 benchmark samples** across 44 cases. Maximum observed verifier RSS was **144,080 KiB**. |
| **Private SDK integration** | **10/10 Linux regression tests** and **9/9 live native integration cases** passed. The verifier binds certificates to expected requests and separates certificate validity, budget satisfaction, and policy authorization. A valid budget-exceeded receipt was denied authorization. |

The quantum contract covers admitted circuits with **X/Z/CX/H**, at most **eight qubits and 64 gates**, and **no pruning**. Exact arithmetic trials and Linux x86-64 native quantum trials are ready within their tested scope. Native ARM64 deployment remains **BLOCKED**. Universal Python-to-Lean correspondence, universal checker equivalence, and authenticated execution provenance remain **OPEN**. Graceful handling of address-space failure remains **OPEN** after a restrictive control exited 139. The historical **Gate 4c strict containment FAIL** remains in effect, and [PR #39](https://github.com/reggaesharkk/SharkByte/pull/39) remains an open research draft. This evidence establishes neither arbitrary Python verification nor general AI security.

## Verified achievements — Google Cloud, Colab, and local systems

**SharkByte's public results span local Windows ARM64, Ubuntu ARM64 under WSL2, Google Colab CPUs, and Google Compute Engine.** These are measured, source-linked experiments with distinct verification methods—not a single claim that every workload is supported by the same execution engine.

| Where it ran | Verified milestone | Evidence |
| --- | --- | --- |
| **Exact inverse-gate simplification** | The opt-in pass cancels **107 nested inverse pairs that become adjacent as the inner pairs cancel** in the original 214-gate, 17-qubit roundtrip circuit while preserving the input source. The certificate records `reference_checked: false`; this is an algebraic identity result, not an independent simulator comparison. | [Roundtrip-17 certificate](evidence/roundtrip17-inverses.json) · [Simplifier tests](tests/test_inverse_simplifier.py) |
| **Opt-in cumulative L2 support compaction** | Exact rational deletion charges compose to an unnormalized L2 bound for finite binary64 inputs under `x`, `z`, and `cx`. The 96 exact-subset configurations are certified; 48 broader gate schedules are explicitly unsupported and separately compared with high-precision references. | [Derivation and limits](docs/certified-bounded-support.md) · [WSL2 evidence](evidence/certified-support-linux.json) |
| **Moving-coordinate protection and adversarial replay** | Exact replay follows protected initial coordinates through `x`, `z`, and `cx`; 444 single-gate/origin mappings and all 322,560 four-qubit affine maps (5,160,960 basis images) are checked. Forged origin, policy, final-map, and protected-deletion receipts are rejected. Mixing operations return `UNSUPPORTED`. | [Windows ARM64](evidence/moving-branch-protection-windows-arm64-v2.json) · [Ubuntu WSL2 ARM64](evidence/moving-branch-protection-ubuntu-wsl2-arm64-v2.json) |
| **Native Windows worker containment** | The opt-in bounded-support Job Object supervisor passed a 42-case Windows ARM64 record, including repeated memory-refusal and timeout cases, with process cleanup accounting. It is scoped to this worker and is not a general sandbox. | [ARM64 containment record](evidence/windows-job-arm64-certified-support-final.json) · [Limits and failures](docs/windows-bounded-job.md) |
| **H3: cumulative Hadamard error ledger** | The standalone composition inequality bounds unnormalized L2 error across restricted `x`, `z`, `cx`, and `h` sequences under explicit binary64 arithmetic assumptions. Independent exact rational replay checks each prefix; native signed-zero bits are not certified. | [Derivation](docs/h3-cumulative-hadamard.md) · [Windows/WSL2 evidence](evidence/h3/) |
| **H4: deterministic software-defined binary64** | An opt-in research runner implements nearest-even and gradual-underflow semantics in software. Independent rational replay reconstructed **matching output bits and charges** on Windows ARM64 and Ubuntu WSL2 ARM64. The nine-gate ledger was **31,730 bytes**; public H certification remains `UNSUPPORTED`. | [Arithmetic contract](docs/h4-software-binary64.md) · [H4 receipts](evidence/h4-gate1/) |
| **H4 archival certificate replay (public)** | The frozen candidate-v1 X/Z/CX/H research certificate can be checked against its pinned Git tree and independently reconstructed under a versioned Gate 4b compatibility policy. The comparator reports exact input, gate-prefix, binary64-word, numerical-charge and budget agreement, **not authenticated execution or a public Hadamard certificate**. | [Historical replay](docs/h4-gate4-historical-checkout.md) · [Gate 4b comparison](docs/h4-gate4b-compatibility.md) · [Archived fixture](evidence/h4-candidate/) |
| **Strict H3/H4 receipt validation** | A separate versioned validator rejects noncanonical rows, duplicate keys, changed event order, altered wrapper fields and forged H4 zero-sign bits. All four archived H3/H4 platform receipts passed strict validation; **who executed them remains unauthenticated**. | [Validation contract](docs/strict-hadamard-receipts.md) · [Hostile tests](tests/test_strict_hadamard_receipt.py) |
| **Google Colab (Linux x86_64)** | The original moving-branch receipt is pinned to the same `7793d5e` source as GCE; its manifest, 13 source hashes, and seven payload fields match GCE and the Windows/WSL records. The recorded execution took **28.67 s**; no fresh Colab run is claimed here. | [Archived Colab ZIP](evidence/gce-moving-branch-cross-platform-20261120/sharkbyte-moving-cloud-evidence.zip) · [Audit and verifier](evidence/gce-moving-branch-cross-platform-20261120/) |
| **GCE cross-platform audit (Linux x86_64)** | The archived source-bound run took **13.96 s** on a host reporting 33,658,982,400 bytes RAM (**31.35 GiB**). The worker used a **24 GiB virtual-address-space ceiling** and had a **55.66 MiB sampled peak VmRSS**. The run matched the pinned Windows ARM64 and WSL2 payload records. | [Original ZIP and audit reports](evidence/gce-moving-branch-cross-platform-20261120/) · [Reproducible verifier](tools/high_support/verify_gce_cross_platform_audit.py) |
| **Google Compute Engine (Linux x86_64)** | **4,294,967,296 packed GHZ-family basis/amplitude entries checked** against a closed-form parity reference. The two array SHA-256 digests matched the independent Colab replay; the temporary packed arrays totaled **96 GiB**. | [GCE 2³² receipt](evidence/connected-ghz50-gcp/2p32/sharkbyte-ghz50-4b-gcp-receipt.json) |
| **Google Colab (Linux x86_64)** | Independently completed the same **4,294,967,296-entry** structured materialization and full-array check. A separate connected **40-qubit / 33,554,432-populated-amplitude** sparse experiment matched its closed-form oracle. | [50-qubit Colab receipt](evidence/connected-ghz50-colab/retry-2p32/sharkbyte-connected-ghz50-4294967296-colab.json) · [40-qubit Colab receipt](evidence/connected-ghz40-32m-colab/sharkbyte-connected-ghz40-33554432-colab.json) |
| **Windows ARM64 (local Studio)** | The fixed **40-qubit / 16,777,216-state** CPU benchmark ran from Studio, recording **2.77 GiB** peak process memory. The unified release also passed **87 local tests** and **17 installed-package acceptance checks**. | [Windows Studio receipt](evidence/studio_16m/windows_arm64/sharkbyte-85c74d14dcb54040a295e3c2fe422e53.json) · [Release integration PR](https://github.com/reggaesharkk/SharkByte/pull/13) |
| **Ubuntu ARM64 under WSL2 (local)** | The same 16-million-state sparse benchmark and independent quantum reference checks were exercised in the documented ARM64 environment. This is **WSL2**, not an independent physical Ubuntu host. | [Ubuntu scaling receipt](benchmarks/sb_quantum_benchmark/scaling-16777216-ubuntu-wsl.json) · [Qiskit/Cirq methods](INDEPENDENT_QUANTUM_VALIDATION.md) |
| **Hosted GitHub Actions (Windows and Ubuntu)** | The combined H4 integration passed all **five applicable workflows** before merging. Hosted Windows CI is x64 and distinct from the separately recorded native ARM64 and WSL2 ARM64 runs. | [Combined integration record (PR #30)](https://github.com/reggaesharkk/SharkByte/pull/30) · [Workflow sources](.github/workflows/) |

**One-click Google Colab notebooks** — open a notebook, select a **CPU runtime**, then choose **Runtime → Run all**.

| Notebook | Verified experiment / scope | Launch |
| --- | --- | --- |
| Certified moving-branch | Exact signed-permutation branch tracking, affine-map closure and independent replay | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Moving-Branch-Certification.ipynb) |
| Integrated verification | 16,777,216-state comparison and scoped checks | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Integrated-Verification.ipynb) |
| Connected 40-qubit | 33,554,432-state sparse GHZ-family experiment | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Connected-40Q-32M.ipynb) |
| Connected 50-qubit | GHZ-family disk materialization, **up to 4,294,967,296 entries** | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Connected-50Q-2B.ipynb) |

**Run requirements:** larger experiments need substantial RAM, disk space, and execution time; a notebook may select a smaller tier or refuse a run. Integrated verification pins a historical revision, not today's `main`.

**Scope:** The 4.29-billion-entry result is **formula-based, disk-backed GHZ-family verification**, not general 50-qubit statevector simulation. Cirq checked a separate 512-shot invariant, not the entire array. The 16-million-state experiment is a separate disconnected CPU sparse workload. The new H3/H4 certificates are also restricted research tools, not extensions of the public certified-support API. [Methods](tools/run_connected_ghz50_materialization.py) · [Full claim boundaries](CLAIM_BOUNDARIES.md).

The audit also examined an archived Colab run. I found and preserved its original ZIP, then checked its receipt digest, manifest, 13 pinned source hashes, and seven payload fields against GCE and the checked-in Windows ARM64 and WSL2 records. This verifies the archived comparison; it does not rerun Colab. The 32 GiB-class GCE host capacity was available, not consumed. Sampled VmRSS is not a strict peak, and `RLIMIT_AS` limits virtual address space rather than resident memory.

---

## H3/H4 Hadamard research: what is established

I separate **a mathematical error inequality**, **an independently replayable ledger**, **bit-level arithmetic reproducibility**, and **authenticated execution provenance**. They are not interchangeable.

| Research stage | Verified scope | Remaining boundary |
| --- | --- | --- |
| **Hadamard foundations (A1/A2)** | Exact rational deletion-charge search and a conditional single-Hadamard L2 allowance under specified nearest-even binary64 semantics. | Not a general floating-point proof for arbitrary native environments. |
| **H3 cumulative ledger** | Gate-by-gate error composition and exact ideal-prefix replay for finite, unnormalized `x/z/cx/h` experiments. Historical Windows and Ubuntu receipts agree mathematically. | Native signed-zero output bits are recorded but not independently reproduced. |
| **H4 software binary64** | Software-defined rounding with independent rational, **bit-exact** gate replay; matching Windows ARM64 and Ubuntu WSL2 ARM64 research ledgers. | Experimental **up to eight qubits, 64 gates**; computational and certificate overhead is significant. |
| **Strict receipt validation** | Canonical H3 sparse states, full wrapper consistency, duplicate-key refusal, event-order checking, strict H4 bits, and external-digest support. | A receipt digest, even one independently pinned, does **not authenticate** the machine, operator, or telemetry. |

The nine-gate H4 fixture produced a **31,730-byte** ledger, approximately **2.94 × 10⁻¹⁶** cumulative L2 allowance, and about **1.86×** native H3 verification time on the two ARM64 hosts. A separate 64-Hadamard, 256-coordinate fixture took substantially longer to replay; these are individual measurements, **not generalized performance claims**.

### H4 compatibility and formal verification status

**Public and merged through Gate 4b:** the pinned candidate-v1 archive has an independent, research-only compatibility checker for bounded, unnormalized X/Z/CX/H circuits (at most eight qubits and 64 ordered gates, with no pruning). It checks intermediate words and numerical charges, not merely final states. [Versioned candidate](docs/h4-versioned-candidate.md) · [Gate 4b specification](docs/h4-gate4b-compatibility.md).

**Gate 4c remains a draft, not part of `main`:** [PR #39](https://github.com/reggaesharkk/SharkByte/pull/39) tests an opt-in OS-contained research comparator. Native Windows ARM64 and Ubuntu WSL2 ARM64 audits report compatible archived-v1 replay, allocation refusals and tested process cleanup. However, the Windows strict *reported peak job commit* acceptance criterion **FAILS**: attempted allocations were refused while peak accounting exceeded the configured limit. The PR is not an accepted strict containment guarantee or an untrusted-code sandbox.

**Private, unpublished Gates 5C–5D:** further independent work reports a bounded mathematical refinement argument and kernel-checked Lean lemmas (word decoding, local rounding rules, coefficient inequalities, selected gate involutions, outward roots, and conditional prefix induction). The full binary64 grid/refinement theorem, Hadamard local L2 enclosure, and correspondence to actual Python implementations are **OPEN**. Private implementation, formal source and receipts are not in this repository; these local research observations are **not publicly reproducible from `main`**, not a new public certificate, and not a release. Candidate-v2 remains **unregistered**.

**Certification boundary:** the installed/public certified-support interface currently certifies the finite binary64 **`x/z/cx` signed-permutation subset only**. Hadamard, renormalization, mixing-gate pruning and arbitrary circuit certification remain **`UNSUPPORTED`** there. Use the standalone H3/H4 research commands below for their own documented guarantees.

[Foundations](docs/hadamard-foundations.md) · [H3 derivation](docs/h3-cumulative-hadamard.md) · [H4 reproducibility](docs/h4-software-binary64.md) · [Strict receipt validator](docs/strict-hadamard-receipts.md) · [Remaining certification gates](docs/h4-certification-gates.md) · [Bounded replay and public H candidate](docs/h4-replay-remediation.md) · [Versioned experimental candidate](docs/h4-versioned-candidate.md) · [Frozen v1 archive replay](docs/h4-candidate-archival-policy.md) · [Gate 4b independent compatibility](docs/h4-gate4b-compatibility.md)

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

**Requirements:** CPython **3.10+**, Git (for cloning), and pip. The ordinary CLI and core SharkByte runtime have **zero required third-party Python runtime dependencies**. Studio's Lucid Dynamics mode uses the optional `lucid` extra (`numpy>=1.26,<3`, `scipy>=1.11,<2`). Independent comparisons may use additional reference packages.

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

### Current integration and historical release checks

The unified Studio integration was introduced by [PR #13](https://github.com/reggaesharkk/SharkByte/pull/13). The later **H3/H4 research and strict-validation integration** was verified on the combined [draft PR #30](https://github.com/reggaesharkk/SharkByte/pull/30) before sequentially merging [PR #28](https://github.com/reggaesharkk/SharkByte/pull/28), [PR #29](https://github.com/reggaesharkk/SharkByte/pull/29), and [PR #31](https://github.com/reggaesharkk/SharkByte/pull/31). These merge commits are source-integration milestones, **not a new tagged package release**.

| Check | Recorded outcome |
| --- | --- |
| **Combined H4 — Windows ARM64** | **174/174 tests passed** on the integrated research revision, as recorded in the local Windows run |
| **Combined H4 — Ubuntu WSL2 ARM64** | **174 tests collected: 169 passed, five skipped** (Windows Job Object tests only). A separate manual run used Python 3.14.4, NumPy 2.5.5, SciPy 1.18.1 |
| **Optional Lucid on Ubuntu** | All **nine tests passed** under normal, `-O`, and `-OO`; NumPy/SciPy were installed only in an isolated environment |
| **Combined H4 GitHub Actions** | **Five applicable workflows passed** on [the draft integration head](https://github.com/reggaesharkk/SharkByte/pull/30); hosted CI uses Windows/Ubuntu **x64** where noted |
| **Historical Studio integration acceptance** | [PR #13](https://github.com/reggaesharkk/SharkByte/pull/13): 87 local Windows ARM64 tests and 17 installed-package checks; historical release baseline, not the latest suite count |
| **Archived H3/H4 evidence** | Four original platform receipts replayed under the [strict validator](docs/strict-hadamard-receipts.md); source hashes and original bytes preserved |

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
| **H3/H4 Hadamard research** | Conditional cumulative error theorem, exact rational per-gate ledger, deterministic H4 binary64 bit replay and strict archival receipt checks | Arbitrary gates, generic hardware attestations, authenticated provenance, or an enabled public H-certified API | [H3](docs/h3-cumulative-hadamard.md) · [H4](docs/h4-software-binary64.md) · [Strict receipt contract](docs/strict-hadamard-receipts.md) |
| **High-support scaling frontier** | 20-qubit circuits filled **1,048,576 sparse dictionary entries** in tested cases; 30-qubit low-support controls retained one or two entries; q24/q28/q30 full-support plans refused before worker launch under the stated 1.5-GiB cap | Arbitrary dense 24–30-qubit simulation, a general sparse speedup or proven large-state compaction efficiency | [Scaling audit](docs/audited-high-support-frontier.md) |
| **20-qubit connected, high-support circuit** | 1,048,576 amplitudes compared across four methods; measured balanced-cut Schmidt rank **1,024** | A general efficient large-qubit simulation method | [Methods and receipts](docs/high-support-connected-entanglement.md) |
| **40-qubit / 16,777,216-state sparse workload** | CPU run and exact independent amplitude comparison for the specified **disconnected** circuit | A dense 40-qubit statevector or globally entangled 40-qubit experiment | [Studio receipt](evidence/studio_16m/windows_arm64/sharkbyte-85c74d14dcb54040a295e3c2fe422e53.json) · [Cirq comparison](evidence/windows-arm64-cirq/cirq-16777216.json) |
| **40-qubit / 33,554,432-state connected GHZ-family workload** | Populated sparse amplitudes matched a closed-form oracle; connected GHZ entanglement has a separate analytical justification | General dense 40-qubit evolution or a full Cirq amplitude replay of this larger state | [Receipt and manifest](evidence/connected-ghz40-32m-colab/) |
| **50-qubit / 4,294,967,296-entry GHZ-family materialization** | Disk-backed packed basis/amplitude arrays exhaustively checked against independent parity calculations; Colab and Google Compute Engine array digests matched | Structured analytical workload; see [scope above](#verified-achievements--google-cloud-colab-and-local-systems) | [Colab receipt](evidence/connected-ghz50-colab/retry-2p32/sharkbyte-connected-ghz50-4294967296-colab.json) · [Compute Engine replay](evidence/connected-ghz50-gcp/2p32/sharkbyte-ghz50-4b-gcp-receipt.json) |
| **Adaptive sparse/dense comparisons** | Repeated CPU benchmarks for three specified 20-qubit cases; full vectors matched the dense candidate | Universal speedup; low-support cases favor sparse storage | [Reports and methodology](evidence/adaptive_sparse_dense/manifest.json) |
| **Lucid Dynamics** | IVc/IVb periods reproduced; memoryless reference decayed; all nine receipts verified | Global stability, formal existence proof, or physiological interpretation | [Nine-receipt audit](docs/lucid-dynamics-audit.md) |

The earlier 2³² `RESOURCE_STOP` attempt is preserved alongside the later successful run in [historical evidence](evidence/connected-ghz50-colab/). The [materialization worker](tools/run_connected_ghz50_materialization.py) and [notebook](notebooks/SharkByte-Colab-Connected-50Q-2B.ipynb) document the exact method.

For the 40-qubit 16-million-state case, the Windows Studio worker recorded approximately **2.77 GiB** peak process memory, while a separate Linux/WSL and Colab reference program compared the populated amplitudes under its documented circuit decomposition. Times are **workload-, hardware-, and environment-specific**, not a generic benchmark against other languages.

Frontier30 can simplify adjacent inverse gates before sparse evolution. Pass `--simplify-inverses` to its benchmark CLI. For roundtrip-17, all 107 pairs cancel and the final sparse dictionary has one entry. The report lists original gate indices in cancellation order.

**Certified numerical subset:** the opt-in exact-error certificate supports finite binary64 initial amplitudes with x, z, and cx signed permutations. Mixing gates, angle gates, decimal conversion error, and renormalization return UNSUPPORTED. See [the derivation and source-bound comparisons](docs/certified-bounded-support.md), including 96 exact-subset configurations and 48 explicitly unsupported legacy configurations compared with high-precision references.

**Opt-in moving-branch protection:** the certified subset can follow selected initial basis-coordinate amplitudes through x, z, and cx gates with `protected_branches=` (or repeated `--protect-branch INITIAL_INDEX` in the bounded runner). This mode rejects mixing gates and is distinct from legacy fixed-index protection; both remain opt-in. It tracks coordinate amplitudes under signed permutations, not physical paths through mixing operations.

**Remaining numerical boundary:** the default simulator can retain tiny floating-point residuals after round trips. The opt-in **public certified-support** compactor is limited to finite binary64 `x/z/cx` signed permutations without normalization. Separately, the standalone **H3/H4 research tools** support bounded `x/z/cx/h` circuits with cumulative error checks and deterministic H4 bit replay, but they do **not** change the public API's supported set or certify mixing-gate support pruning generally. [Round-trip control](evidence/colab-q8w4bj57/roundtrip-17/roundtrip_17q_comparison.json) · [H4 scope](docs/h4-software-binary64.md) · [Public subset](docs/certified-bounded-support.md).

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

# Independently verify the archived GCE moving-branch evidence and source hashes
python -B tools/high_support/verify_gce_cross_platform_audit.py

# Research-only: strictly validate an archived H3 receipt and its outer wrapper
python -B -m tools.high_support.strict_hadamard_receipt archive evidence/h3/circuit.json evidence/h3/windows-arm64.json

# Research-only: seal and strictly verify an existing H4 experimental receipt
python -B -m tools.high_support.strict_hadamard_receipt seal evidence/h3/circuit.json evidence/h4-gate1/windows-arm64.json > strict.json
python -B -m tools.high_support.strict_hadamard_receipt verify evidence/h3/circuit.json strict.json
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
- **Not general certified Hadamard execution.** The standalone H3/H4 experiments have finite, unnormalized, resource-bounded semantics. The public certified-support API still returns `UNSUPPORTED` for `h`.
- **Not a production compiler or unrestricted language implementation.** The [grammar](GRAMMAR.md) and [specification](SPEC.md) document an intentionally bounded alpha subset.
- **Not a security sandbox.** The native interpreter and Direct AArch64 execution remain **disabled**. The Windows Job Object supervisor contains only the opt-in bounded-support generation/replay worker on tested systems; that evidence does not establish containment for arbitrary SharkByte programs. Do not execute untrusted inputs in sensitive environments. [Supervisor limits](docs/windows-bounded-job.md) · [Security policy](SECURITY.md).
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
| [docs/audited-high-support-frontier.md](docs/audited-high-support-frontier.md) · [Hadamard proof obligations](docs/hadamard-certification-proof-obligations.md) | Resource-bounded scaling and historically open Hadamard certification obligations |
| [Hadamard mathematical foundations](docs/hadamard-foundations.md) · [H3 cumulative ledger](docs/h3-cumulative-hadamard.md) | Conditional A1/A2 and exact ideal-prefix composition |
| [H4 software-defined arithmetic](docs/h4-software-binary64.md) · [H4 certification gates](docs/h4-certification-gates.md) | Deterministic binary64 replay and remaining open integration requirements |
| [Strict receipt validation](docs/strict-hadamard-receipts.md) | Canonical archived H3/H4 receipt semantics, tamper checks and unauthenticated execution provenance |
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

The complete checkout suite covers features that are not included in the installed CLI-only package. The acceptance script deliberately tests the installed distribution **outside** the source tree. Core CI runs on Windows and Ubuntu. The nine Lucid tests need the optional `lucid` extra; Windows Job Object tests are intentionally skipped on Linux. Hosted CI is **not** a substitute for native Windows ARM64, WSL2 ARM64, or large Colab/GCE workloads. Review [the workflows](.github/workflows/) and [current verification records](#current-integration-and-historical-release-checks).

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

**SharkByte's central proposition is testable computation:** write a bounded program, run the appropriate engine, preserve a source-bound record, and check the result against the right independent reference. H3/H4 now extend this discipline to restricted Hadamard research, while the public certification boundary remains intentionally narrower. A larger calculation is not necessarily a stronger claim.
