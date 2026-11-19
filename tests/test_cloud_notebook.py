"""Static, offline checks for the pinned Colab reproduction notebook."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/SharkByte-Colab-Moving-Branch-Certification.ipynb"
PINNED = "7793d5eace34456ce1cc57f85f4d75cf84c8e889"


class CloudNotebookTests(unittest.TestCase):
    def test_notebook_is_well_formed_and_python_compiles(self):
        notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(len(notebook["cells"]), 5)
        sources = []
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                source = "".join(cell["source"])
                compile(source, f"colab-cell-{index}", "exec")
                sources.append(source)
        self.assertEqual(len(sources), 4)
        joined = "\n".join(sources)
        self.assertIn('PINNED_SOURCE = "' + PINNED + '"', joined)
        self.assertIn('PREFLIGHT_REFUSED = WORKER_AS_BYTES < GIB', joined)
        self.assertIn('os.killpg(proc.pid, signal.SIGKILL)', joined)
        self.assertIn('check_moving_branch_protection.py', joined)
        self.assertIn('files.download(str(archive))', joined)

    def test_one_click_and_claim_boundaries_are_linked(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "docs/cloud-moving-branch-verification.md").read_text(encoding="utf-8")
        self.assertIn('SharkByte-Colab-Moving-Branch-Certification.ipynb', readme)
        self.assertIn(PINNED, guide)
        self.assertIn('32 GiB', guide)
        self.assertIn('RLIMIT_AS', guide)
        self.assertIn('not', guide.lower())


if __name__ == "__main__":
    unittest.main()
