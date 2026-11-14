import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sharkbyte_alpha.cli import envelope

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless((ROOT / "sharkbyte_terminal.py").is_file(), "requires a source checkout")
class TerminalExperiments(unittest.TestCase):
    def test_project_explanations_use_grounded_answers(self):
        prompts = (
            "Explain what /qft computed on the 30-qubit register and why the spectator qubits stay 0.",
            "Explain what the Bell phase demo shows.",
        )
        output = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(ROOT / "sharkbyte_terminal.py")],
            input="\n".join((*prompts, "/quit")) + "\n", cwd=ROOT,
            text=True, encoding="utf-8", capture_output=True, check=True, timeout=30,
        ).stdout
        self.assertIn("not entangled with the active six-qubit register", output)
        self.assertIn("all four outcomes at 25% each", output)
        self.assertNotIn("SharkByte model:", output)

    def test_save_verify_and_replay(self):
        from sharkbyte_experiment import replay
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "my circuit.sb").write_text(
                "qubits 1;\nshots 16;\nseed 8;\nx 0;\nmeasure_all;\n", encoding="utf-8"
            )

            def terminal(*commands):
                return subprocess.run(
                    [sys.executable, "-X", "utf8", "-B", str(ROOT / "sharkbyte_terminal.py")],
                    input="\n".join((*commands, "/quit")) + "\n", cwd=path,
                    text=True, encoding="utf-8", capture_output=True, check=True, timeout=30,
                ).stdout

            for command, mode in (('/run "my circuit.sb"', "quantum"),
                                  ("/bell-phase", "bell-phase"), ("/qft", "frontier")):
                name = mode + ".json"
                terminal(command, f"/save {name}")
                output = terminal(f"/verify {name}", f"/replay {name}")
                self.assertIn("INTEGRITY_VERIFIED", output)
                self.assertIn("REPLAY_MATCH", output)

            saved = path / "quantum.json"
            receipt = json.loads(saved.read_text(encoding="utf-8"))
            receipt["result"]["counts"] = {"0": 16, "1": 0}
            saved.write_text(json.dumps(receipt), encoding="utf-8")
            self.assertIn("record hash mismatch", terminal("/verify quantum.json"))
            with self.assertRaisesRegex(ValueError, "REPLAY_MISMATCH"):
                replay(envelope(receipt["source"], "quantum", receipt["result"]))

            over_budget = ROOT / "benchmarks" / "sb_quantum_benchmark" / "branch13.sb"
            output = terminal(f'/run-frontier "{over_budget}"', "/save refused.json")
            self.assertIn("4096", output)
            self.assertFalse((path / "refused.json").exists())
