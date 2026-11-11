"""Compare the package with the scoped public Qiskit probability vectors."""
import argparse,hashlib,json,pathlib,platform,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sharkbyte_alpha import __version__,cli,quantum
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--output",type=pathlib.Path,default=pathlib.Path("QISKIT_CANDIDATE_COMPARISON.json"));a=ap.parse_args()
 root=ROOT;ev=root/"evidence"/"qiskit_0.2.2a1";v=json.loads((ev/"qiskit_probability_comparison.json").read_text());r=json.loads((ev/"INDEPENDENT_EVIDENCE_REVIEW.json").read_text())
 rows=[];ma=ml=mn=0.;states=0
 for name,ref in v["fixtures"].items():
  src=(ev/"fixtures"/(name+".sbq")).read_bytes();qasm=(ev/"fixtures"/(name+".qasm")).read_bytes();c=cli.parse_quantum(src.decode());out=quantum.to_qasm(c).encode()
  if out!=qasm:raise SystemExit("QASM byte mismatch: "+name)
  b=r["fixtures"][name]
  if sha(src)!=b["source_sha256"] or sha(out)!=b["qasm_sha256"]:raise SystemExit("fixture digest mismatch: "+name)
  act=quantum.evaluate(c)["probabilities"];exp=ref["probabilities"]
  if set(act)!=set(exp):raise SystemExit("basis-label mismatch: "+name)
  err=[abs(float(act[k])-float(exp[k])) for k in exp];ae=max(err,default=0.);l1=sum(err);ne=abs(sum(float(x) for x in act.values())-1.)
  ma=max(ma,ae);ml=max(ml,l1);mn=max(mn,ne);states+=len(exp);rows.append({"fixture":name,"basis_states":len(exp),"max_probability_error":ae,"l1_distribution_error":l1,"normalization_error":ne,"source_sha256":sha(src),"qasm_sha256":sha(out),"status":"PASS"})
  if ae>1e-9 or l1>1e-8 or ne>1e-10:raise SystemExit("tolerance exceeded: "+name)
 if len(rows)!=22 or states!=320:raise SystemExit("fixture inventory mismatch")
 report={"schema":1,"status":"PASS","candidate_version":__version__,"reference":"scoped archived Ubuntu Qiskit 2.6.2 vectors from package 0.2.2a1","host":{"system":platform.system(),"architecture":platform.machine(),"python":platform.python_version()},"endianness":"q0 least-significant; labels MSB-left; QASM c[i] maps to q[i]","tolerances":{"per_state_absolute":1e-9,"l1_distribution":1e-8,"normalization":1e-10},"summary":{"fixtures":len(rows),"basis_state_probabilities":states,"max_per_state_absolute_error":ma,"max_l1_distribution_error":ml,"max_normalization_error":mn},"fixtures":rows}
 a.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8");print(json.dumps(report["summary"],sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
