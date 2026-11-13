# Local backend agreement

Run with Python 3 on Ubuntu AArch64 with clang and lld. Set SHARKBYTE_NATIVE_ROOT to the absolute path of the existing 8093 development tree containing backend/, runtime/, and reference/. The laptop defaults to its existing D: audit tree.

    python3 -B benchmarks/backend_agreement/check_backend_agreement.py

Use trusted local programs with the standalone runner. The archived Ubuntu WSL run passed nine cases on three backends. The receipt records source and compiled artifact hashes. Runtime dependencies are supplied by the local development tree.
