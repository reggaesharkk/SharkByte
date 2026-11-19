"""Internal phases of the Windows bounded-support supervisor."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import traceback


def run_module(name, args, stream):
    sys.argv = [name, *args]
    with contextlib.redirect_stdout(stream):
        runpy.run_module("benchmarks.sb_quantum_benchmark."+name, run_name="__main__")


def main():
    phase, directory, source, *args = sys.argv[1:]
    directory = Path(directory)
    stage = directory/"completed"
    with (directory/"diagnostics.log").open("a", encoding="utf-8") as log:
        try:
            if phase == "generate":
                with stage.open("x", encoding="utf-8", newline="\n") as stream:
                    run_module("bounded_support", [source, *args], stream)
            elif phase in ("validate", "verify"):
                receipt = stage
                if phase == "verify":
                    receipt = directory/"input.json"
                    shutil.copyfile(args[0], receipt)
                run_module("verify_bounded", [source, str(receipt)], log)
                with receipt.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                if phase == "verify":
                    stage.write_text(json.dumps(dict(verified=True,receipt_sha256=digest)),encoding="ascii")
                (directory/"receipt.sha256").write_text(digest,encoding="ascii")
            elif phase == "publish":
                # Same-volume, create-only atomic publication of already closed bytes.
                os.rename(stage, args[0])
            else:
                raise ValueError("unknown worker phase")
        except MemoryError:
            print("MemoryError", file=log)
            return 86
        except Exception:
            traceback.print_exc(file=log)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
