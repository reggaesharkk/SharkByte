"""Verify the sanitized public Qiskit reference fixtures and scoped provenance."""
import hashlib, json, pathlib, unittest
from sharkbyte_alpha import cli, quantum
ROOT=pathlib.Path(__file__).resolve().parents[1]
PACKAGE=pathlib.Path(cli.__file__).resolve().parent
EVIDENCE=ROOT/"evidence"/"qiskit_0.2.2a1"
FIXTURES=EVIDENCE/"fixtures"
VECTORS=json.loads((EVIDENCE/"qiskit_probability_comparison.json").read_text(encoding="utf-8"))
REVIEW=json.loads((EVIDENCE/"INDEPENDENT_EVIDENCE_REVIEW.json").read_text(encoding="utf-8"))
sha=lambda b:hashlib.sha256(b).hexdigest()
class IndependentQiskitAcceptance(unittest.TestCase):
 def test_scoped_module_provenance(self):
  p=REVIEW["source_provenance"]
  self.assertEqual(p["package_version"],"0.2.2a1"); self.assertEqual(p["candidate_package_version"],"0.2.1a2")
  self.assertEqual(p["cli_module_sha256"],"9e2e92b5e483ac170880c4dad86d81713104aef08f5ec799b694a8edc8ed40ed")
  self.assertEqual(p["quantum_module_sha256"],"ed020bd7b1c18167c2d91179b2295935d5210e665a9487759f6c793b88903eb1")
  self.assertEqual(sha((ROOT/"tests/fixtures/historical_qiskit_cli.py.txt").read_bytes()),p["candidate_cli_sha256"])
  self.assertEqual(sha((PACKAGE/"quantum.py").read_bytes()),p["candidate_quantum_sha256"])
  self.assertEqual(p["candidate_cli_sha256"],p["cli_module_sha256"]); self.assertEqual(p["candidate_quantum_sha256"],p["quantum_module_sha256"])
  self.assertEqual(p["whole_package_identity"],"NOT_CLAIMED")
 def test_public_evidence_manifest(self):
  m=json.loads((EVIDENCE/"PUBLIC_EVIDENCE_MANIFEST.json").read_text(encoding="utf-8"))
  for e in m["files"]:
   b=(EVIDENCE/e["path"]).read_bytes(); self.assertEqual(len(b),e["bytes"],e["path"]); self.assertEqual(sha(b),e["sha256"],e["path"])
 def test_all_22_qasm_files_and_full_probability_vectors(self):
  cases=VECTORS["fixtures"]; bindings=REVIEW["fixtures"]; self.assertEqual(len(cases),22); self.assertEqual(set(cases),set(bindings))
  states=0; max_abs=max_l1=0.0
  for name,ref in cases.items():
   with self.subTest(fixture=name):
    source=(FIXTURES/(name+".sbq")).read_bytes(); qasm=(FIXTURES/(name+".qasm")).read_bytes()
    circuit=cli.parse_quantum(source.decode("utf-8")); emitted=quantum.to_qasm(circuit).encode("utf-8")
    self.assertEqual(sha(source),bindings[name]["source_sha256"]); self.assertEqual(sha(emitted),bindings[name]["qasm_sha256"]); self.assertEqual(emitted,qasm)
    actual=quantum.evaluate(circuit)["probabilities"]; expected=ref["probabilities"]; self.assertEqual(set(actual),set(expected))
    errs=[abs(float(actual[k])-float(expected[k])) for k in expected]; ae=max(errs,default=0.0); l1=sum(errs)
    max_abs=max(max_abs,ae); max_l1=max(max_l1,l1); states+=len(expected)
    self.assertLessEqual(ae,1e-9,name); self.assertLessEqual(l1,1e-8,name); self.assertAlmostEqual(sum(actual.values()),1.0,delta=1e-10); self.assertEqual(ref["status"],"PASS")
  self.assertEqual(states,320); self.assertLessEqual(max_abs,1e-9); self.assertLessEqual(max_l1,1e-8)
if __name__=="__main__": unittest.main(verbosity=2)
