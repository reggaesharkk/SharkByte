"""Apply the worker address-space limit before importing the benchmark stack."""
from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "benchmarks" / "sb_quantum_benchmark" / "support_scaling.py"


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: studio_scaling_worker.py MEMORY_LIMIT_BYTES STATES PROGRESS_FILE")
    memory_limit, states = int(sys.argv[1]), int(sys.argv[2])
    if memory_limit < 1 or states != (1 << 24):
        raise SystemExit("invalid fixed benchmark resource parameters")
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    benchmark_dir = str(SCRIPT.parent)
    if benchmark_dir not in sys.path:
        sys.path.insert(0, benchmark_dir)
    sys.argv = [str(SCRIPT), str(states), "--progress-file", sys.argv[3]]
    runpy.run_path(str(SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()
