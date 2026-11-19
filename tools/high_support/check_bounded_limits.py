"""Exercise Linux child limits on a real roundtrip certificate."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    launcher = [sys.executable, str(root/"tools/high_support/limit_bounded.py")]
    source = root/"examples/high_support/roundtrip_17q.sbq"
    generate = ["generate", str(source), "--support-cap", "131072", "--memory-mib", "256",
                "--seconds", "180", "--interval", "214", "--budget", "1e-10"]
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        receipt = Path(directory)/"record.json"
        verify = ["verify", str(source), str(receipt)]
        for operation in (generate, verify):
            for mib, seconds, expected in [(512,180,"pass"),(32,180,"memory"),(512,0.05,"timeout")]:
                cmd = launcher + ["--address-mib",str(mib),"--seconds",str(seconds)] + operation
                proc = subprocess.run(cmd,cwd=root,capture_output=True)
                if expected == "pass":
                    assert proc.returncode == 0, proc.stderr
                    if operation == generate:
                        receipt.write_bytes(proc.stdout)
                elif expected == "timeout":
                    assert proc.returncode == 124 and not proc.stdout, proc.stderr
                else:
                    assert proc.returncode != 0 and b"MemoryError" in proc.stderr and not proc.stdout, proc.stderr
                cases.append(dict(operation=operation[0],address_mib=mib,seconds=seconds,
                                  outcome=expected,exit=proc.returncode))
        print(json.dumps(dict(receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
                              receipt_bytes=receipt.stat().st_size,
                              source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                              cases=cases),indent=2))


if __name__ == "__main__":
    main()
