# Three-backend agreement on Linux ARM64

This benchmark compiles the same nine SharkByte programs with the bundled reference toolchain and checks SharkVM, Direct AArch64, and the AArch64 native interpreter against hand-derived results. It compares stdout, exit status, and expected error diagnostics and records SHA-256 hashes of the sources and compiled artifacts.

On Ubuntu ARM64 (including ARM64 WSL), clone or download SharkByte, open a terminal in the repository root, and run:

```sh
sudo apt-get install clang lld
python3 -B benchmarks/backend_agreement/check_backend_agreement.py
python3 -B benchmarks/backend_agreement/check_all_budgets.py
```

Python 3.10+ is required. The checkout supplies the compiler, reference VM and native runtime sources. An optional `SHARKBYTE_NATIVE_ROOT` override supports testing another compatible toolchain tree. Leave it unset for the public benchmark.

Expect `27/27 passed` from the agreement suite and a pass for each backend from the budget check. The budget check runs a nonterminating loop and expects the execution-limit diagnostic. The configured limit is 50,000,000 VM instructions or native ticks according to the backend's accounting. The suite prints the path to its fresh JSON receipt. Build directories are unique per invocation and ignored by Git. Compiler and linker versions can affect ELF hashes.

The [archived Ubuntu WSL receipt](ubuntu-wsl-results.json) records a prior laptop run. GitHub Actions publishes fresh Linux ARM64 receipts under the `backend-agreement-ubuntu-arm64` artifact.

Use the standalone runner with trusted local programs. This suite measures functional agreement and budget refusal. Host isolation remains unverified and the installed standalone CLI keeps native execution disabled.
