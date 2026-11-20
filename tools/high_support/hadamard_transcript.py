"""Print or replay a standalone Hadamard research transcript."""
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

from hadamard_foundations import enclose
from replay_hadamard_foundations import verify


def source_hashes():
    return {name: hashlib.sha256(Path(__file__).with_name(name).read_text(encoding="ascii").encode("ascii")).hexdigest()
            for name in ("hadamard_foundations.py", "replay_hadamard_foundations.py",
                         "hadamard_transcript.py")}


def main():
    if len(sys.argv) == 2:
        report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        if report["source_sha256"] != source_hashes():
            raise ValueError("source hash mismatch")
        if verify(report["pair"]) != report["decision"]:
            raise ValueError("decision mismatch")
        print("PASS")
        return
    start = perf_counter()
    pair = enclose(complex(-0., 1.), complex(0., -1.))
    decision = verify(pair)
    print(json.dumps({"source_sha256": source_hashes(), "pair": pair, "decision": decision,
                      "platform": platform.platform(), "machine": platform.machine(),
                      "python": platform.python_version(), "elapsed_seconds": perf_counter()-start},
                     indent=2))


if __name__ == "__main__":
    main()
