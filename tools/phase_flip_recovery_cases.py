"""Run the Studio phase-flip recovery example and its analytical controls."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sharkbyte_alpha.cli import envelope, parse_quantum, verify
from sharkbyte_alpha.quantum import evaluate


def main():
    source = (ROOT / "examples" / "phase_flip_recovery.sb").read_text(encoding="utf-8")
    before, recovery = source.split("    // BEGIN RECOVERY\n", 1)
    _, after = recovery.split("    // END RECOVERY\n", 1)
    cases = []
    for error, syndrome in ((None, "00"), (0, "01"), (1, "11"), (2, "10")):
        modes = ("recovery_on",) if error is None else ("recovery_on", "recovery_off")
        for mode in modes:
            case = source if mode == "recovery_on" else before + after
            case = case.replace("    z 1;\n", "" if error is None else f"    z {error};\n", 1)
            cases.append((mode, error, syndrome, case, float(mode == "recovery_on")))

    wrong_phase = source.replace("cp 1.0471975511965976 3 0", "cp -1.0471975511965976 3 0", 1)
    cases.append(("wrong_phase", 1, "11", wrong_phase, 0.25))
    for first, second, syndrome in ((0, 1, "10"), (0, 2, "11"), (1, 2, "01")):
        circuit = source.replace("    z 1;\n", f"    z {first}; z {second};\n", 1)
        # The resulting logical X has squared overlap cos(pi/3)^2.
        cases.append(("two_errors", [first, second], syndrome, circuit, 0.25))
    evidence = []
    for mode, error, syndrome, circuit, expected in cases:
        result = evaluate(parse_quantum(circuit))
        probabilities = result["probabilities"]
        syndrome_probability = sum(p for bits, p in probabilities.items() if bits[:2] == syndrome)
        overlap_probability = probabilities[syndrome + "000"]
        if abs(syndrome_probability - 1) > 1e-12 or abs(overlap_probability - expected) > 1e-12:
            raise RuntimeError(f"Unexpected syndrome or recovery probability in {mode}, Z={error}")
        receipt = envelope(circuit, "quantum", result)
        verify(receipt)
        evidence.append(dict(case=mode, error_qubit=error, syndrome=syndrome,
                             expected_overlap_probability=expected, receipt=receipt))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
