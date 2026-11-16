"""Compare complete vectors, source identity, and entanglement witnesses."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.high_support.common import analytic_phase_matrix, entanglement_metrics, generate_plan, is_two_qubit_graph_connected, render_source, sha256

BACKENDS=("qiskit","cirq","dense","sparse")
AMPLITUDE_TOL=2e-10
PROBABILITY_MAX_TOL=2e-10
PROBABILITY_L1_TOL=2e-9
NORM_TOL=1e-10


def aligned_metrics(expected, actual):
    overlap=np.vdot(expected,actual)
    phase=overlap/abs(overlap) if abs(overlap)>0 else 1+0j
    aligned=actual*np.conjugate(phase)
    diff=np.abs(expected-aligned)
    p0=np.abs(expected)**2
    p1=np.abs(actual)**2
    pd=np.abs(p0-p1)
    return {"max_amplitude_error_after_global_phase_alignment":float(diff.max(initial=0.0)),
            "l2_amplitude_error_after_global_phase_alignment":float(np.linalg.norm(diff)),
            "max_probability_error":float(pd.max(initial=0.0)),
            "l1_probability_error":float(pd.sum(dtype=np.float64)),
            "expected_norm":float(np.vdot(expected,expected).real),
            "actual_norm":float(np.vdot(actual,actual).real),
            "global_phase_radians":float(np.angle(phase))}


def load_backend(case,width,backend,runs_dir,source_hash,gate_hash):
    stem=f"{case}_{width}q_{backend}"
    receipt_path=runs_dir/(stem+".json")
    vector_path=runs_dir/(stem+".npy")
    receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
    raw=vector_path.read_bytes()
    if receipt["status"]!="PASS": raise ValueError(f"backend receipt status is not PASS: {stem}")
    if receipt["source_sha256"]!=source_hash or receipt["parsed_source_sha256"]!=source_hash:
        raise ValueError(f"source identity mismatch: {stem}")
    if receipt["gate_sequence_sha256"]!=gate_hash or receipt["parsed_gate_sequence_sha256"]!=gate_hash:
        raise ValueError(f"gate identity mismatch: {stem}")
    if sha256(raw)!=receipt["saved_npy_sha256"]: raise ValueError(f"saved vector file hash mismatch: {stem}")
    vector=np.load(vector_path,allow_pickle=False)
    canonical=np.ascontiguousarray(vector,dtype=np.dtype("<c16"))
    if sha256(canonical.tobytes(order="C"))!=receipt["state_vector_sha256_little_endian_complex128"]:
        raise ValueError(f"state vector hash mismatch: {stem}")
    return receipt,canonical


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case",choices=("entangled","random_connected","connected_separable","numerical_adversary","roundtrip"),required=True)
    parser.add_argument("--width",type=int,required=True)
    parser.add_argument("--source-dir",type=Path,required=True)
    parser.add_argument("--plan-dir",type=Path,required=True)
    parser.add_argument("--runs-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    plan=generate_plan(args.width,args.case)
    source=args.source_dir/f"{args.case}_{args.width}q.sbq"
    source_raw=source.read_bytes()
    source_hash=sha256(source_raw)
    if source_raw!=render_source(plan): raise ValueError("source differs from deterministic rendering")
    plan_path=args.plan_dir/f"{args.case}_{args.width}q.plan.json"
    plan_raw=plan_path.read_bytes()
    stored_plan=json.loads(plan_raw)
    expected_plan=dict(plan,source_sha256=source_hash)
    if stored_plan!=expected_plan: raise ValueError("stored plan differs from deterministic generator/source")
    plan_hash=sha256(plan_raw)
    if not is_two_qubit_graph_connected(plan): raise ValueError("two-qubit interaction graph is not connected")
    gate_hash=plan["gate_sequence_sha256"]
    records={}
    states={}
    for backend in BACKENDS:
        receipt,state=load_backend(args.case,args.width,backend,args.runs_dir,source_hash,gate_hash)
        if len(state)!=(1<<args.width): raise ValueError(f"statevector length mismatch: {backend}")
        records[backend]=receipt
        states[backend]=state
    reference=states["qiskit"]
    pairwise={}
    for backend in BACKENDS:
        pairwise[backend]=aligned_metrics(reference,states[backend])
    checks={
        "all_backends_used_same_source_bytes":len({r["source_sha256"] for r in records.values()})==1,
        "all_backends_used_same_gate_sequence":len({r["gate_sequence_sha256"] for r in records.values()})==1,
        "all_backends_returned_full_vector":all(len(v)==(1<<args.width) for v in states.values()),
        "all_norms_within_tolerance":all(abs(x["actual_norm"]-1.0)<=NORM_TOL for x in pairwise.values()),
        "all_amplitudes_match_qiskit":all(x["max_amplitude_error_after_global_phase_alignment"]<=AMPLITUDE_TOL for x in pairwise.values()),
        "all_probabilities_match_qiskit":all(x["max_probability_error"]<=PROBABILITY_MAX_TOL and x["l1_probability_error"]<=PROBABILITY_L1_TOL for x in pairwise.values()),
        "interaction_graph_connected":True}
    details={"source_sha256":source_hash,"plan_file_sha256":plan_hash,"gate_sequence_sha256":gate_hash,
             "comparison_code_sha256":sha256(Path(__file__).read_bytes()),
             "corpus_generator_sha256":sha256((ROOT/"validation"/"high_support"/"common.py").read_bytes()),
             "numpy_version":np.__version__,
             "qubits":args.width,"gates":len(plan["gates"]),"case":args.case,
             "backend_measurements":{name:{"active_amplitudes_exact_nonzero":r["active_amplitudes_exact_nonzero"],
                                             "norm":r["norm"],"median_elapsed_seconds":r["median_elapsed_seconds"],
                                             "peak_rss_bytes_process_lifetime":r["peak_rss_bytes_process_lifetime"],
                                             "backend_run_details":r["backend_run_details"],
                                             "state_vector_sha256":r["state_vector_sha256_little_endian_complex128"]}
                                     for name,r in records.items()},
             "comparison_to_qiskit":pairwise,
             "tolerances":{"amplitude_max":AMPLITUDE_TOL,"probability_max":PROBABILITY_MAX_TOL,
                           "probability_l1":PROBABILITY_L1_TOL,"normalization":NORM_TOL}}
    if args.case in ("entangled","random_connected"):
        oracle=analytic_phase_matrix(plan)
        oracle_metrics=entanglement_metrics(oracle.T.reshape(-1),args.width,plan["split"])
        reference_metrics={name:entanglement_metrics(states[name],args.width,plan["split"])
                           for name in ("qiskit","cirq")}
        spectra={name:np.asarray(value["singular_values"],dtype=np.float64)
                 for name,value in reference_metrics.items()}
        oracle_spectrum=np.asarray(oracle_metrics["singular_values"],dtype=np.float64)
        spectrum_errors={name:float(np.max(np.abs(spectra[name]-oracle_spectrum),initial=0.0))
                         for name in reference_metrics}
        cut=plan["split"]
        details["entanglement"]={"partition":{"A_qubits":list(range(cut)),"B_qubits":list(range(cut,args.width))},
                                 "witness_method":"Schmidt spectrum of independently simulated complete statevector; analytic controlled-phase matrix provides a separate oracle because within-partition CX and final single-qubit rotations are local unitaries across this cut.",
                                 "analytic_phase_matrix":{k:v for k,v in oracle_metrics.items() if k!="singular_values"},
                                 "backend_schmidt_metrics":{name:{k:v for k,v in metric.items() if k!="singular_values"}
                                                            for name,metric in reference_metrics.items()},
                                 "max_singular_value_error_vs_analytic_oracle":spectrum_errors}
        checks["qiskit_schmidt_rank_exceeds_one"]=reference_metrics["qiskit"]["schmidt_rank_at_relative_cutoff"]>1
        checks["cirq_schmidt_rank_exceeds_one"]=reference_metrics["cirq"]["schmidt_rank_at_relative_cutoff"]>1
        checks["reference_spectra_match_analytic_oracle"]=all(value<=2e-10 for value in spectrum_errors.values())
        checks["all_backends_produce_dense_support"]=all(r["active_amplitudes_exact_nonzero"]==(1<<args.width) for r in records.values())
    elif args.case in ("connected_separable","numerical_adversary"):
        cut=plan["split"]
        metrics={name:entanglement_metrics(states[name],args.width,cut) for name in ("qiskit","cirq")}
        details["entanglement"]={"witness_method":"Schmidt spectrum of Qiskit and Cirq full statevectors across the balanced cut.",
                                 "backend_schmidt_metrics":{name:{k:v for k,v in metric.items() if k!="singular_values"} for name,metric in metrics.items()}}
        checks["qiskit_schmidt_rank_is_one"]=metrics["qiskit"]["schmidt_rank_at_relative_cutoff"]==1
        checks["cirq_schmidt_rank_is_one"]=metrics["cirq"]["schmidt_rank_at_relative_cutoff"]==1
        checks["control_has_dense_support"]=all(r["active_amplitudes_exact_nonzero"]==(1<<args.width) for r in records.values())
        if args.case=="numerical_adversary":
            limit=4.0*math.pi
            angles=[abs(float(g[3] if g[0]=="cp" else g[2])) for g in plan["gates"] if g[0] in ("cp","rx","ry","rz")]
            details["numerical_adversary"]={"angle_limit":limit,"maximum_absolute_angle":max(angles),"near_limit_offset":1e-12,"all_angles_within_limit":max(angles)<=limit}
            checks["angles_within_4pi_limit"]=max(angles)<=limit
            checks["near_limit_angles_exercised"]=any(abs(value-(limit-1e-12))<1e-15 for value in angles)
    else:
        leakage={name:float(np.max(np.abs(state[1:]),initial=0.0)) for name,state in states.items()}
        target_probability={name:float(abs(state[0])**2) for name,state in states.items()}
        details["roundtrip"]={"expected_basis_state":"0"*args.width,
                              "max_off_target_amplitude":leakage,
                              "target_probability":target_probability,
                              "exact_nonzero_support_by_backend":{name:int(np.count_nonzero(np.abs(state)>0.0)) for name,state in states.items()},
                              "note":"Floating residual amplitudes are reported; no threshold pruning is applied.",
                              "sparse_support_compaction_status":"OPEN" if np.count_nonzero(np.abs(states["sparse"])>0.0)>1 else "PASS"}
        checks["all_backends_return_to_zero_within_tolerance"]=all(leakage[name]<=5e-10 and abs(target_probability[name]-1)<=1e-10 for name in BACKENDS)
    checks["all_checks_pass"]=all(checks.values())
    report={"schema":1,"status":"PASS" if checks["all_checks_pass"] else "FAIL",
            "case":args.case,"qubits":args.width,"checks":checks,"results":details}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"case":args.case,"width":args.width,
                      "checks":checks,"entanglement":details.get("entanglement"),
                      "roundtrip":details.get("roundtrip")},indent=2))
    return 0 if report["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())