"""Build a path-redacted SHA-256 manifest for a high-support run bundle."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys


def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def revision(root: Path):
    try:
        return subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo",type=Path,required=True)
    parser.add_argument("--sources",type=Path,required=True)
    parser.add_argument("--plans",type=Path,required=True)
    parser.add_argument("--results",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    root=args.repo.resolve()
    files=[]
    for label,folder in (("sources",args.sources),("plans",args.plans),("results",args.results)):
        folder=folder.resolve()
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.resolve()==args.output.resolve():
                continue
            files.append({"path":f"{label}/{path.relative_to(folder).as_posix()}",
                          "bytes":path.stat().st_size,"sha256":digest(path)})
    report={"schema":1,"revision":revision(root),"host":platform.platform(),
            "architecture":platform.machine(),"python":sys.version.split()[0],
            "files":files,"file_count":len(files),
            "note":"Unkeyed SHA-256 identifies exact bytes; it does not establish authorship or correctness."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"manifest":str(args.output),"file_count":len(files),"revision":report["revision"]}))

if __name__=="__main__":
    main()