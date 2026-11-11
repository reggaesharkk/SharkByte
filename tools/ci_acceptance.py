"""Install and test the package outside its source checkout."""
import argparse,hashlib,json,os,pathlib,platform,shutil,subprocess,sys,tempfile,venv
def run(cmd,cwd,env,timeout=180):return subprocess.run(cmd,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,text=True,encoding="utf-8",errors="replace")
def test_count(s):
 import re;m=re.search(r"Ran (\d+) tests?",s);return int(m.group(1)) if m else 0
def json_ok(p,pred):
 try:return p.returncode==0 and pred(json.loads(p.stdout))
 except Exception:return False
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--work-dir",type=pathlib.Path);ap.add_argument("--build-wheelhouse",type=pathlib.Path);ap.add_argument("--report",type=pathlib.Path);a=ap.parse_args();root=pathlib.Path(__file__).resolve().parents[1]
 base=a.work_dir.resolve() if a.work_dir else None
 if base:
  base.mkdir(parents=True,exist_ok=True)
  if base==root or root in base.parents or base in root.parents:raise SystemExit("work directory must be outside source checkout")
 tmp=tempfile.TemporaryDirectory(prefix="sharkbyte-public-ci-",dir=str(base) if base else None);w=pathlib.Path(tmp.name);checks=[];fail=[];modes={};smoke=[]
 def check(n,ok,d=""):
  checks.append({"name":n,"status":"PASS" if ok else "FAIL","detail":d})
  if not ok:fail.append(n)
 try:
  vd=w/"venv";venv.EnvBuilder(with_pip=True).create(vd);py=vd/("Scripts/python.exe" if os.name=="nt" else "bin/python");exe=vd/("Scripts/sharkbyte.exe" if os.name=="nt" else "bin/sharkbyte")
  env=os.environ.copy();env.pop("PYTHONPATH",None);env.pop("PYTHONHOME",None);env["PYTHONNOUSERSITE"]="1";env["PIP_DISABLE_PIP_VERSION_CHECK"]="1"
  cmd=[str(py),"-m","pip","install","--no-deps"]
  if a.build_wheelhouse:
   wh=a.build_wheelhouse.resolve()
   if not wh.is_dir():raise SystemExit("build wheelhouse not found")
   cmd += ["--no-index","--find-links",str(wh)]
  cmd += [str(root)];p=run(cmd,w,env,240);check("isolated_pep517_install",p.returncode==0,"exit="+str(p.returncode))
  if p.returncode:raise RuntimeError("isolated package installation failed")
  fixture=w/"fixture";fixture.mkdir()
  for n in ("tests","examples","evidence"):shutil.copytree(root/n,fixture/n)
  ident=run([str(py),"-c","import pathlib,sharkbyte_alpha;print(pathlib.Path(sharkbyte_alpha.__file__).resolve())"],fixture,env,20);ip=pathlib.Path(ident.stdout.strip()).resolve()
  check("installed_import_outside_checkout",ident.returncode==0 and root not in ip.parents,"exit="+str(ident.returncode))
  sp=root/"sharkbyte_alpha";dp=ip.parent;files=sorted(x for x in sp.rglob("*") if x.is_file() and x.suffix in (".py",".json"));matched=0
  for x in files:
   y=dp/x.relative_to(sp)
   if not y.is_file() or hashlib.sha256(x.read_bytes()).digest()!=hashlib.sha256(y.read_bytes()).digest():break
   matched+=1
  check("installed_source_identity",matched==len(files),str(matched)+"/"+str(len(files)))
  for flags,name in (([],"normal"),(["-O"],"O"),(["-OO"],"OO")):
   p=run([str(py),*flags,"-m","unittest","discover","-s","tests","-v"],fixture,env,240);ok=p.returncode==0 and "OK" in p.stderr
   modes[name]={"status":"PASS" if ok else "FAIL","exit_code":p.returncode,"tests_run":test_count(p.stderr)};check("tests_"+name,ok,"tests="+str(modes[name]["tests_run"])+"; exit="+str(p.returncode))
  def smoke_one(n,args,pred):
   p=run([str(exe),*args],fixture,env,45);ok=pred(p);smoke.append({"name":n,"status":"PASS" if ok else "FAIL","exit_code":p.returncode});check("smoke_"+n,ok,"exit="+str(p.returncode));return p
  smoke_one("version",["--version"],lambda p:p.returncode==0 and "0.2.1a2" in p.stdout)
  smoke_one("doctor",["doctor"],lambda p:p.returncode==0)
  smoke_one("classical",["run","examples/example.sb","--backend","vm"],lambda p:json_ok(p,lambda d:d.get("result",{}).get("stdout")=="42\n" and d["result"].get("vm_instruction_count")==5))
  smoke_one("quantum",["run","examples/bell.sb","--mode","quantum"],lambda p:json_ok(p,lambda d:abs(sum(d["result"]["probabilities"].values())-1.)<1e-10))
  smoke_one("hybrid",["run","examples/adaptive.sb","--mode","hybrid","--backend","vm"],lambda p:json_ok(p,lambda d:d["result"].get("iterations_executed")==4))
  for b in ("native_interpreter","direct_native"):
   smoke_one("native_guard_"+b,["run","examples/example.sb","--backend",b],lambda p:p.returncode==1 and not p.stdout and "native backends are disabled: containment unavailable" in p.stderr)
  report={"schema":1,"status":"FAIL" if fail else "PASS","candidate":"SharkByte standalone alpha 0.2.1a2 public source copy","host":{"system":platform.system(),"architecture":platform.machine(),"python":platform.python_version()},"checks":checks,"summary":{"check_count":len(checks),"failures":fail,"optimization_test_runs":modes,"installed_source_files_compared":matched,"smoke_checks":smoke,"native_functionality":"DISABLED; guard refusals are negative tests only"}}
  if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
  print(json.dumps(report,sort_keys=True));return int(bool(fail))
 except Exception as e:
  print(json.dumps({"status":"FAIL","error_type":type(e).__name__,"message":str(e),"checks":checks},sort_keys=True));return 1
 finally:tmp.cleanup()
if __name__=="__main__":raise SystemExit(main())
