"""Linux process limits for certificate generation and replay, including JSON I/O."""
import argparse
import math
import resource
import subprocess
import sys
import tempfile


def run(operation, arguments, address_mib, seconds):
    if address_mib < 1 or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("positive memory and wall-clock limits required")
    limit = address_mib * 1024**2

    def constrain():
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    module = {"generate": "bounded_support", "verify": "verify_bounded"}[operation]
    cmd = [sys.executable, "-m", "benchmarks.sb_quantum_benchmark." + module, *arguments]
    # Publish stdout only after successful completion; child output stays on disk.
    with tempfile.TemporaryFile() as output:
        try:
            result = subprocess.run(cmd, preexec_fn=constrain, stdout=output, timeout=seconds)
        except subprocess.TimeoutExpired:
            return 124
        if result.returncode == 0:
            import shutil
            output.seek(0)
            shutil.copyfileobj(output, sys.stdout.buffer)
        return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address-mib", type=int, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("operation", choices=("generate","verify"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    sys.exit(run(args.operation, args.arguments, args.address_mib, args.seconds))
