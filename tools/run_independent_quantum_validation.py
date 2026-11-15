"""Run and persist the independent SharkByte / Qiskit Statevector suite."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.independent_qiskit.suite import run_validations  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True,
                        help="new JSON receipt path; an existing file is never overwritten")
    args = parser.parse_args()
    report = run_validations()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit("refusing to overwrite existing result: " + str(output))
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": report["status"], "result": str(output),
                      "revision": report["revision"], "summary": report["summary"]},
                     sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
