"""Reproduce certified-subset cases against exact, NumPy, Qiskit and Cirq references."""
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import warnings

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

import cirq
import mpmath as mp
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from benchmarks.sb_quantum_benchmark.certified_support import certify, _root_interval
from benchmarks.sb_quantum_benchmark.bounded_support import simulate as bounded_simulate
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit, evolve as sparse_evolve


BASE="9cb5c45a74cbfd9def184e607d4aeafedbe316d1"


def git_revision():
    try:
        return subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    except Exception:
        return None


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def gate_hash(gates):
    return sha_bytes(json.dumps(gates,separators=(",",":")).encode())


def fractions(state):
    return {basis:(Fraction(value.real),Fraction(value.imag)) for basis,value in state.items()}


def exact_evolve(width, gates, initial):
    state=fractions(initial)
    for gate in gates:
        op=gate[0]
        if op=="x":
            bit=1<<gate[1]
            state={basis^bit:value for basis,value in state.items()}
        elif op=="cx":
            control,target=1<<gate[1],1<<gate[2]
            state={basis^target if basis&control else basis:value
                   for basis,value in state.items()}
        elif op=="z":
            bit=1<<gate[1]
            state={basis:((-value[0],-value[1]) if basis&bit else value)
                   for basis,value in state.items()}
        else:
            raise ValueError(op)
    return state


def dense_reference(width,gates,initial):
    vector=np.zeros(1<<width,dtype=np.complex128)
    for basis,value in initial.items():
        vector[basis]=value
    for gate in gates:
        output=np.zeros_like(vector)
        op=gate[0]
        for basis,value in enumerate(vector):
            if op=="x":
                target=basis^(1<<gate[1])
                output[target]=value
            elif op=="cx":
                target=basis^((1<<gate[2]) if basis&(1<<gate[1]) else 0)
                output[target]=value
            elif op=="z":
                output[basis]=(-value if basis&(1<<gate[1]) else value)
            elif op=="h":
                bit=1<<gate[1]
                if basis&bit:
                    continue
                low,high=value,vector[basis|bit]
                output[basis]=(low+high)/math.sqrt(2.0)
                output[basis|bit]=(low-high)/math.sqrt(2.0)
            elif op in ("rx","ry"):
                bit=1<<gate[1]
                if basis&bit:
                    continue
                low,high=value,vector[basis|bit]
                c,s=math.cos(gate[2]/2),math.sin(gate[2]/2)
                if op=="rx":
                    output[basis]=c*low-1j*s*high
                    output[basis|bit]=c*high-1j*s*low
                else:
                    output[basis]=c*low-s*high
                    output[basis|bit]=s*low+c*high
            elif op=="rz":
                phase=np.exp(0.5j*gate[2])
                output[basis]=phase*value if basis&(1<<gate[1]) else phase.conjugate()*value
            elif op=="cp":
                mask=(1<<gate[1])|(1<<gate[2])
                phase=np.exp(1j*gate[3])
                output[basis]=phase*value if basis&mask==mask else value
            else:
                raise ValueError(op)
        vector=output
    return vector


def independent_refs(width,gates,initial):
    qc=QuantumCircuit(width)
    q=cirq.LineQubit.range(width)
    cc=cirq.Circuit()
    for gate in gates:
        op=gate[0]
        if op=="x":
            qc.x(gate[1]); cc.append(cirq.X(q[gate[1]]))
        elif op=="z":
            qc.z(gate[1]); cc.append(cirq.Z(q[gate[1]]))
        elif op=="cx":
            qc.cx(gate[1],gate[2]); cc.append(cirq.CNOT(q[gate[1]],q[gate[2]]))
        elif op=="h":
            qc.h(gate[1]); cc.append(cirq.H(q[gate[1]]))
        elif op=="rx":
            qc.rx(gate[2],gate[1]); cc.append(cirq.rx(gate[2])(q[gate[1]]))
        elif op=="ry":
            qc.ry(gate[2],gate[1]); cc.append(cirq.ry(gate[2])(q[gate[1]]))
        elif op=="rz":
            qc.rz(gate[2],gate[1]); cc.append(cirq.rz(gate[2])(q[gate[1]]))
        elif op=="cp":
            qc.cp(gate[3],gate[1],gate[2])
            cc.append(cirq.CZPowGate(exponent=gate[3]/math.pi)(q[gate[1]],q[gate[2]]))
    vector=dense_reference(width,(),initial)
    qiskit_state=np.asarray(Statevector(vector).evolve(qc).data,dtype=np.complex128)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cirq_state=np.asarray(cirq.Simulator(dtype=np.complex128).simulate(
            cc,initial_state=vector,qubit_order=q[::-1]).final_state_vector,dtype=np.complex128)
    warning_messages=[str(item.message) for item in caught]
    if any("skipping renormalization" not in message for message in warning_messages):
        raise AssertionError(warning_messages)
    dense_state=dense_reference(width,gates,initial)
    return dense_state,qiskit_state,cirq_state,warning_messages


def exact_float_error_squared(left, right):
    total=Fraction(0)
    for a,b in zip(left,right):
        dr=Fraction(*complex(a).real.as_integer_ratio())-Fraction(*complex(b).real.as_integer_ratio())
        di=Fraction(*complex(a).imag.as_integer_ratio())-Fraction(*complex(b).imag.as_integer_ratio())
        total += dr*dr + di*di
    return total


def fraction_record(value):
    return f"{value.numerator}/{value.denominator}"


def _mpf_exact_fraction(raw):
    sign,mantissa,exponent,_=raw
    numerator=-mantissa if sign else mantissa
    if exponent>=0:
        return Fraction(numerator<<exponent,1)
    return Fraction(numerator,1<<(-exponent))


def _fraction_interval(value):
    value=Fraction(value)
    return mp.iv.mpf([value.numerator,value.numerator])/value.denominator


def interval_reference(width,gates,initial):
    """Enclose exact binary64 inputs and ideal gate operations with mpmath.iv."""
    mp.iv.dps=100
    zero=mp.iv.mpc(0,0)
    vector=[zero for _ in range(1<<width)]
    for basis,value in initial.items():
        vector[basis]=mp.iv.mpc(_fraction_interval(Fraction(*value.real.as_integer_ratio())),
                                _fraction_interval(Fraction(*value.imag.as_integer_ratio())))
    inv_sqrt2=mp.iv.sqrt(mp.iv.mpf(1)/2)
    for gate in gates:
        op=gate[0]
        if op=="x":
            bit=1<<gate[1]
            vector=[vector[basis^bit] for basis in range(1<<width)]
        elif op=="cx":
            cb,tb=1<<gate[1],1<<gate[2]
            vector=[vector[basis^(tb if basis&cb else 0)] for basis in range(1<<width)]
        elif op=="z":
            bit=1<<gate[1]
            vector=[-value if basis&bit else value for basis,value in enumerate(vector)]
        elif op=="h":
            bit=1<<gate[1]
            nxt=list(vector)
            for basis in range(1<<width):
                if basis&bit:
                    continue
                low,high=vector[basis],vector[basis|bit]
                nxt[basis]=(low+high)*inv_sqrt2
                nxt[basis|bit]=(low-high)*inv_sqrt2
            vector=nxt
        elif op in ("rx","ry"):
            bit=1<<gate[1]
            theta=_fraction_interval(Fraction(*float(gate[2]).as_integer_ratio()))
            cosine,sine=mp.iv.cos(theta/2),mp.iv.sin(theta/2)
            nxt=list(vector)
            for basis in range(1<<width):
                if basis&bit:
                    continue
                low,high=vector[basis],vector[basis|bit]
                if op=="rx":
                    nxt[basis]=cosine*low-1j*sine*high
                    nxt[basis|bit]=cosine*high-1j*sine*low
                else:
                    nxt[basis]=cosine*low-sine*high
                    nxt[basis|bit]=sine*low+cosine*high
            vector=nxt
        elif op=="rz":
            bit=1<<gate[1]
            theta=_fraction_interval(Fraction(*float(gate[2]).as_integer_ratio()))
            cosine,sine=mp.iv.cos(theta/2),mp.iv.sin(theta/2)
            phase=mp.iv.mpc(cosine,sine)
            conjugate=mp.iv.mpc(cosine,-sine)
            vector=[value*(phase if basis&bit else conjugate)
                    for basis,value in enumerate(vector)]
        elif op=="cp":
            cb,tb=1<<gate[1],1<<gate[2]
            theta=_fraction_interval(Fraction(*float(gate[3]).as_integer_ratio()))
            phase=mp.iv.mpc(mp.iv.cos(theta),mp.iv.sin(theta))
            vector=[value*phase if basis&cb and basis&tb else value
                    for basis,value in enumerate(vector)]
        else:
            raise ValueError(op)
    bounds=[]
    for value in vector:
        re_lo,re_hi=value.real._mpi_
        im_lo,im_hi=value.imag._mpi_
        bounds.append((_mpf_exact_fraction(re_lo),_mpf_exact_fraction(re_hi),
                       _mpf_exact_fraction(im_lo),_mpf_exact_fraction(im_hi)))
    return bounds


def interval_bounds_hash(bounds):
    records=[[fraction_record(component) for component in row] for row in bounds]
    return sha_bytes(json.dumps(records,separators=(",",":")).encode())


def interval_uncertainty_squared(bounds):
    return sum(((re_hi-re_lo)**2+(im_hi-im_lo)**2
                for re_lo,re_hi,im_lo,im_hi in bounds),Fraction(0))


def full_vector(state,width):
    vector=np.zeros(1<<width,dtype=np.complex128)
    if isinstance(state,dict):
        for basis,value in state.items():
            vector[basis]=value
    else:
        vector[:]=state
    return vector


def interval_error_squared_upper(bounds,vector):
    total=Fraction(0)
    for (re_lo,re_hi,im_lo,im_hi),value in zip(bounds,vector):
        real=Fraction(*float(complex(value).real).as_integer_ratio())
        imag=Fraction(*float(complex(value).imag).as_integer_ratio())
        dre=max(abs(real-re_lo),abs(real-re_hi))
        dim=max(abs(imag-im_lo),abs(imag-im_hi))
        total+=dre*dre+dim*dim
    return total


def binary_reference_hash(state):
    records=[[basis,str(value[0].numerator),str(value[0].denominator),
              str(value[1].numerator),str(value[1].denominator)]
             for basis,value in sorted(state.items())]
    return sha_bytes(json.dumps(records,separators=(",",":")).encode())


def random_cases():
    rows=[]
    reference_rows=[]
    for width in (2,4,7,12):
        for seed in range(4):
            rng=random.Random(0xC3A7+100*width+seed)
            gates=[]
            for _ in range(96):
                op=rng.choice(("x","z","cx"))
                if op=="cx":
                    a,b=rng.sample(range(width),2); gates.append((op,a,b))
                else:
                    gates.append((op,rng.randrange(width)))
            indices=sorted(rng.sample(range(1<<width),min(24,1<<width)))
            initial={}
            for index in indices:
                real=math.ldexp(float(rng.randint(-31,31) or 1),rng.randint(-900,-5))
                imag=math.ldexp(float(rng.randint(-31,31) or -1),rng.randint(-900,-5))
                initial[index]=complex(real,imag)
            circuit=Circuit(width,tuple(gates),f"certified-{width}-{seed}")
            reference=exact_evolve(width,gates,initial)
            np_ref,qiskit_ref,cirq_ref,cirq_warnings=independent_refs(width,gates,initial)
            canonical=np.zeros(1<<width,dtype=np.complex128)
            for basis,(real,imag) in reference.items():
                canonical[basis]=complex(float(real),float(imag))
            if not np.array_equal(np_ref,canonical) or not np.array_equal(qiskit_ref,canonical) or not np.array_equal(cirq_ref,canonical):
                raise AssertionError("independent vector mismatch")
            for budget in ("1e-100","1e-8","0.01"):
                for interval in (1,17):
                    result=certify(circuit,initial,budget,support_cap=32,
                                   memory_budget_bytes=32*2048,interval=interval)
                    if result["status"]!="PASS":
                        raise AssertionError(result)
                    v=result["verification"]
                    if v["status"]!="PASS":
                        raise AssertionError(v)
                    compact_vector=np.zeros(1<<width,dtype=np.complex128)
                    for basis,value in result["state"].items():
                        compact_vector[basis]=value
                    reference_errors={}
                    for label,reference_vector in (("numpy",np_ref),("qiskit",qiskit_ref),("cirq",cirq_ref)):
                        mass=exact_float_error_squared(compact_vector,reference_vector)
                        if mass > Fraction(v["certified_l2_bound"])**2:
                            raise AssertionError((label,mass,v))
                        reference_errors[label]=dict(squared_error=fraction_record(mass),
                            sqrt_interval=_root_interval(mass),within_bound=True)
                    rows.append(dict(width=width,seed=seed,budget=budget,interval=interval,
                                     exact_reference_uncertainty="0",
                                     gate_sha256=gate_hash(gates),
                                     initial_sha256=result["certificate"]["initial_state_sha256"],
                                     reference_sha256=binary_reference_hash(reference),
                                     certificate_bound=v["certified_l2_bound"],
                                     exact_squared_error=v["exact_squared_error"],
                                     exact_l2_interval=v["exact_l2_interval"],
                                     independent_full_vector_errors=reference_errors,
                                     event_count=len(result["certificate"]["ledger"]["events"]),
                                     final_support=len(result["state"])))
            if seed==0:
                reference_rows.append(dict(width=width,seed=seed,gate_sha256=gate_hash(gates),
                    exact_reference_sha256=binary_reference_hash(reference),
                    numpy_exact=np.array_equal(np_ref,canonical),
                    qiskit_exact=np.array_equal(qiskit_ref,canonical),
                    cirq_exact=np.array_equal(cirq_ref,canonical),
                    exact_reference_uncertainty="0",
                    cirq_skipped_renormalization_warnings=cirq_warnings,
                    initial_components=len(initial)))
    return rows,reference_rows


def legacy_numerical_replay():
    audited=json.loads((ROOT/"evidence/bounded-audit.json").read_text())
    if len(audited["fuzz"])!=48:
        raise AssertionError("archived experiment no longer contains 48 configurations")
    circuits={}
    refs={}
    reference_rows=[]
    rows=[]
    for schedule in audited["fuzz"]:
        width,seed=schedule["width"],schedule["seed"]
        key=(width,seed)
        if key not in circuits:
            rng=random.Random(seed+100*width)
            gates=[]
            for _ in range(5):
                for op in ("ry","h","rx","cx","cp","x","rz","z"):
                    a,b=rng.sample(range(width),2)
                    angle=rng.choice([1e-6,-1e-4,.31,-1.17])
                    gates.append((op,a,b) if op=="cx" else
                                 (op,a,b,angle) if op=="cp" else
                                 (op,a,angle) if op in ("rx","ry","rz") else (op,a))
            digest=gate_hash(gates)
            circuits[key]=(tuple(gates),digest)
            initial={0:1+0j}
            circuit=Circuit(width,tuple(gates),f"legacy-{width}-{seed}")
            bounds=interval_reference(width,gates,initial)
            dense,qiskit_ref,cirq_ref,cirq_warnings=independent_refs(width,gates,initial)
            unpruned=sparse_evolve(circuit,support_cap=1<<width,
                                   memory_budget_bytes=(1<<width)*2048)
            vectors={"numpy":dense,"qiskit":qiskit_ref,"cirq":cirq_ref,
                     "sparse":full_vector(unpruned,width)}
            refs[key]=(bounds,circuit,initial,vectors)
            uncertainty=interval_uncertainty_squared(bounds)
            reference_rows.append(dict(width=width,seed=seed,gate_sha256=digest,
                exact_angle_semantics="each input angle is its exact binary64 dyadic value",
                high_precision_backend="mpmath.iv",
                interval_bits=mp.iv.prec,reference_interval_sha256=interval_bounds_hash(bounds),
                reference_uncertainty_l2_diameter_upper_squared=fraction_record(uncertainty),
                reference_uncertainty_l2_diameter_upper=_root_interval(uncertainty),
                independent_full_vector_errors={name:dict(
                    squared_error_upper=fraction_record(interval_error_squared_upper(bounds,value)),
                    l2_error_upper=_root_interval(interval_error_squared_upper(bounds,value)))
                    for name,value in vectors.items()},
                cirq_warnings=cirq_warnings))
        gates,digest=circuits[key]
        if schedule["gates_sha256"]!=digest:
            raise AssertionError("legacy fuzz gate hash mismatch")
        circuit=Circuit(width,gates,f"legacy-{width}-{seed}")
        initial={0:1+0j}
        answer=certify(circuit,initial,schedule["budget"],support_cap=1<<width,
                       memory_budget_bytes=(1<<width)*2048,interval=schedule["interval"])
        if answer["status"]!="UNSUPPORTED":
            raise AssertionError(answer)
        compacted,ledger=bounded_simulate(circuit,schedule["budget"],
            support_cap=1<<width,memory_budget_bytes=(1<<width)*2048,
            interval=schedule["interval"])
        bounds,_,_,vectors=refs[key]
        compact_vector=full_vector(compacted,width)
        compact_error=interval_error_squared_upper(bounds,compact_vector)
        budget=Fraction(schedule["budget"])
        backend_errors={name:exact_float_error_squared(compact_vector,value)
                        for name,value in vectors.items() if name in ("numpy","qiskit","cirq")}
        paired_sparse_error=exact_float_error_squared(compact_vector,vectors["sparse"])
        rows.append(dict(width=width,seed=seed,budget=schedule["budget"],
            interval=schedule["interval"],gate_sha256=digest,
            certification_status=answer["status"],reason=answer["reason"],
            final_support=len(compacted),event_count=len(ledger["events"]),
            charged_l2=ledger["charged_l2"],
            high_precision_error_squared_upper=fraction_record(compact_error),
            high_precision_l2_error_upper=_root_interval(compact_error),
            full_vector_errors_vs_independent={name:dict(
                squared_error=fraction_record(error),l2_error_interval=_root_interval(error))
                for name,error in backend_errors.items()},
            compacted_vs_unpruned_sparse_squared_difference=fraction_record(paired_sparse_error),
            compacted_vs_unpruned_sparse_l2_interval=_root_interval(paired_sparse_error),
            empirical_error_within_requested_budget=compact_error<=budget*budget))
    if len(rows)!=48 or len(reference_rows)!=12:
        raise AssertionError("legacy replay did not cover 48 schedules and 12 circuits")
    return rows,reference_rows


def adversarial():
    cases=[
      ("minimum-subnormal",Circuit(4,(("x",0),("cx",0,1),("z",2))),
       {0:1+0j,1:complex(math.ulp(0.0),0),2:complex(-2*math.ulp(0.0),math.ulp(0.0))},"1e-320",()),
      ("near-budget",Circuit(4,(("x",0),("z",0),("cx",0,3))),
       {0:1+0j,1:complex(math.nextafter(1e-6,0),0)},"1e-6",()),
      ("fixed-protection-moves",Circuit(4,(("x",0),)),
       {2:1+0j,1:complex(1e-7,0)},"1e-6",(1,)),
      ("repeated-pruning",Circuit(4,(("cx",0,1),("cx",1,0))),
       {8:1+0j,1:complex(2e-5,0),2:complex(3e-5,-1e-5)},"1e-4",(2,)),
    ]
    results=[]
    for name,circuit,initial,budget,protected in cases:
        result=certify(circuit,initial,budget,support_cap=8,memory_budget_bytes=8*2048,
                       interval=1,protected=protected)
        if result["status"]!="PASS":
            raise AssertionError((name,result))
        if name=="repeated-pruning" and len(result["certificate"]["ledger"]["events"]) < 2:
            raise AssertionError("repeated-pruning control did not prune twice")
        results.append(dict(name=name,status=result["status"],
            input_sha256=result["certificate"]["initial_state_sha256"],
            circuit_sha256=result["certificate"]["circuit_sha256"],
            budget=result["certificate"]["requested_budget"],
            bound=result["verification"]["certified_l2_bound"],
            exact_squared_error=result["verification"]["exact_squared_error"],
            event_count=len(result["certificate"]["ledger"]["events"]),
            removed=[r for e in result["certificate"]["ledger"]["events"] for r in e["removed"]],
            final_support=len(result["state"]),
            protection_semantics="fixed basis indices; permutation gates do not move the protected set"))
    unsupported=[]
    for name,gates in [
        ("hadamard-cancellation",[("h",0),("h",0),("h",0),("h",0)]),
        ("destructive-interference",[("h",0),("cx",0,1),("h",0),("cx",0,1)]),
        ("angle-input",[("ry",0,1e-300)]),
    ]:
        answer=certify(Circuit(2,tuple(gates)),{0:1+0j,1:-1+0j},"1e-8",
                       support_cap=4,memory_budget_bytes=8192)
        if answer["status"]!="UNSUPPORTED":
            raise AssertionError(answer)
        unsupported.append(dict(name=name,status=answer["status"],reason=answer["reason"]))
    return results,unsupported


def interference_references():
    delta=math.nextafter(1.0,0.0)
    tiny=math.ulp(0.0)
    cases=[
        ("exact-destructive-cancellation",1,(('h',0),),{0:1+0j,1:-1+0j}),
        ("near-destructive-cancellation",1,(('h',0),),{0:1+0j,1:complex(-delta,0)}),
        ("subnormal-under-hadamard",1,(('h',0),),{0:1+0j,1:complex(tiny,0)}),
        ("tiny-rotation-survives",1,(('ry',0,2.0**-52),),{0:1+0j}),
        ("coherent-recombination",2,(('h',0),('cx',0,1),('h',0),('cx',0,1)),
         {0:1+0j,1:complex(-delta,0),2:complex(tiny,0)}),
    ]
    records=[]
    for name,width,gates,initial in cases:
        circuit=Circuit(width,gates,name)
        bounds=interval_reference(width,gates,initial)
        dense,qiskit_ref,cirq_ref,cirq_warnings=independent_refs(width,gates,initial)
        vectors={"numpy":dense,"qiskit":qiskit_ref,"cirq":cirq_ref,
                 "sparse":full_vector(sparse_evolve(circuit,support_cap=1<<width,
                     memory_budget_bytes=(1<<width)*2048,initial_state=initial),width)}
        answer=certify(circuit,initial,"1e-12",support_cap=1<<width,
                       memory_budget_bytes=(1<<width)*2048)
        if answer["status"]!="UNSUPPORTED":
            raise AssertionError((name,answer))
        uncertainty=interval_uncertainty_squared(bounds)
        errors={label:interval_error_squared_upper(bounds,vector)
                for label,vector in vectors.items()}
        records.append(dict(name=name,width=width,gates=gates,
            gate_sha256=gate_hash(gates),initial_sha256=sha_bytes(json.dumps(
                [[basis,value.real.hex(),value.imag.hex()] for basis,value in sorted(initial.items())],
                separators=(",",":")).encode()),
            certification_status=answer["status"],reason=answer["reason"],
            exact_angle_semantics="binary64 dyadic inputs under ideal gate formulas",
            high_precision_backend="mpmath.iv",interval_bits=mp.iv.prec,
            reference_interval_sha256=interval_bounds_hash(bounds),
            reference_uncertainty_l2_diameter_upper_squared=fraction_record(uncertainty),
            independent_full_vector_errors={label:dict(
                squared_error_upper=fraction_record(error),l2_error_upper=_root_interval(error))
                for label,error in errors.items()},cirq_warnings=cirq_warnings))
    return records


if __name__=="__main__":
    fuzz,refs=random_cases()
    adversaries,unsupported=adversarial()
    legacy,legacy_refs=legacy_numerical_replay()
    interference=interference_references()
    tracked=["benchmarks/sb_quantum_benchmark/certified_support.py",
             "benchmarks/sb_quantum_benchmark/bounded_support.py",
             "benchmarks/sb_quantum_benchmark/sparse_backend.py",
             "tools/high_support/check_certified_support.py",
             "tools/high_support/check_platform_regressions.py",
             "tests/test_certified_support.py",
             "README.md","CLAIM_BOUNDARIES.md","REPRODUCIBILITY.md",
             "docs/certified-bounded-support.md",
             ".github/workflows/certified-support.yml",
             "requirements-high-support.txt",
             "requirements-independent-quantum.txt",
             "evidence/bounded-audit.json"]
    record=dict(base_commit=BASE,head_commit=git_revision(),
        exact_reference_uncertainty="0 for Fraction oracle",
        sqrt_display_interval_bits=1200,python=__import__("sys").version,platform=__import__("platform").platform(),
        versions={name:importlib.metadata.version(name) for name in ("numpy","qiskit","cirq-core","mpmath")},
        hashes={path:sha_bytes((ROOT/path).read_bytes()) for path in tracked},
        certified_configurations=fuzz,independent_reference_cases=refs,
        legacy_48_unsupported=legacy,legacy_high_precision_references=legacy_refs,
        adversarial=adversaries,interference_high_precision_references=interference,
        explicitly_unsupported=unsupported,
        empirical_legacy_schedules_within_budget=sum(
            row["empirical_error_within_requested_budget"] for row in legacy))
    print(json.dumps(record,indent=2))
