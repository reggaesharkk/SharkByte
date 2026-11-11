# Installation and development checks

Requirements: CPython 3.10 or newer; no runtime dependencies. PEP 517 build isolation uses pinned `setuptools==84.2.0`. A package index connection is needed unless a local wheelhouse contains that exact backend.

```sh
python -m venv .venv
python -m pip install .
sharkbyte --version
sharkbyte doctor
```

Keep normal build isolation enabled; do not use `--no-build-isolation` to claim a clean install.

Examples:

```sh
sharkbyte run examples/example.sb --backend vm
sharkbyte run examples/bell.sb --mode quantum
sharkbyte run examples/adaptive.sb --mode hybrid --backend vm
sharkbyte qasm examples/bell.sb --output bell.qasm
```

Run the full acceptance with `python tools/ci_acceptance.py`. It creates a fresh environment, installs this source tree, runs tests outside the checkout under normal/`-O`/`-OO`, and checks both native guard refusals. The guard checks are negative tests only.

Run the scoped archived-vector comparison with `python tools/replay_qiskit_vectors.py --output qiskit-replay.json`; it does not install or invoke Qiskit.
