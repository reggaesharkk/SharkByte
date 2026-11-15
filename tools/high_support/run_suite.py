"""Run one selected high-support source on all four independent backends."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"tools"/"high_support"/"run_backend.py"
COMPARATOR=ROOT/"tools"/"high_support"/"compare.py"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case",choices=("entangled","random_connected","connected_separable","numerical_adversary","roundtrip"),required=True)
    parser.add_argument("--width",type=int,required=True)
    parser.add_argument("--source-dir",type=Path,default=ROOT/"examples"/"high_support")
    parser.add_argument("--plan-dir",type=Path,default=ROOT/"validation"/"high_support"/"plans")
    parser.add_argument("--output-dir",type=Path,required=True)
    parser.add_argument("--repeat",type=int,default=1)
    parser.add_argument("--delete-vectors-after-comparison",action="store_true")
    args=parser.parse_args()
    env=os.environ.copy()
    env["MPLBACKEND"]="Agg"
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for backend in ("qiskit","cirq","dense","sparse"):
        command=[sys.executable,"-B",str(RUNNER),"--case",args.case,"--width",str(args.width),
                 "--backend",backend,"--source-dir",str(args.source_dir),
                 "--output-dir",str(args.output_dir),"--repeat",str(args.repeat)]
        subprocess.run(command,cwd=ROOT,env=env,check=True)
    comparison=args.output_dir/f"{args.case}_{args.width}q_comparison.json"
    command=[sys.executable,"-B",str(COMPARATOR),"--case",args.case,"--width",str(args.width),
             "--source-dir",str(args.source_dir),"--plan-dir",str(args.plan_dir),
             "--runs-dir",str(args.output_dir),"--output",str(comparison)]
    subprocess.run(command,cwd=ROOT,env=env,check=True)
    if args.delete_vectors_after_comparison:
        for vector in args.output_dir.glob(f"{args.case}_{args.width}q_*.npy"):
            vector.unlink()
    print(f"Comparison receipt: {comparison}")

if __name__=="__main__":
    main()