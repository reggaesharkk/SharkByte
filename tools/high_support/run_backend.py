"""Execute one deterministic high-support source on an explicitly selected backend."""
from __future__ import annotations
import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmarks" / "sb_quantum_benchmark"
for path in (ROOT, BENCH, ROOT / "tools" / "high_support"):
    sys.path.insert(0, str(path)) if str(path) not in sys.path else None
from validation.high_support.common import WIDTHS, canonical_json, gate_descriptors, generate_plan, render_source, sha256
from frontier30 import load_circuit


def revision():
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        gitfile = ROOT / ".git"
        if os.name != "nt" and gitfile.is_file():
            match = re.search(r"gitdir:\s*([A-Za-z]):[/\\](.*)", gitfile.read_text(encoding="utf-8"), re.I)
            if match:
                gitdir = Path("/mnt") / match.group(1).lower() / Path(match.group(2).replace("\\", "/"))
                env = os.environ.copy()
                env["GIT_DIR"] = str(gitdir)
                env["GIT_WORK_TREE"] = str(ROOT)
                try:
                    return subprocess.check_output(["git", "rev-parse", "HEAD"], env=env, text=True,
                                                   stderr=subprocess.DEVNULL).strip()
                except Exception:
                    pass
        return None


def peak_rss_bytes():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                       ctypes.byref(counters), counters.cb)
        return int(counters.PeakWorkingSetSize) if ok else None
    try:
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value * (1024 if platform.system() != "Darwin" else 1))
    except Exception:
        return None


def execute(backend, circuit, expected_gates):
    gates = circuit.gates
    if backend == "sparse":
        import numpy as np
        import sparse_backend
        cap = 1 << circuit.qubits
        stats = sparse_backend.EvolutionStats()
        started = time.perf_counter()
        result = sparse_backend.evolve(circuit, support_cap=cap,
                                       memory_budget_bytes=cap * sparse_backend.ESTIMATED_BYTES_PER_AMPLITUDE,
                                       max_seconds=240, stats=stats)
        evolution_seconds = time.perf_counter() - started
        started = time.perf_counter()
        state = np.zeros(cap, dtype=np.complex128)
        for index, amplitude in result.items():
            state[index] = amplitude
        materialization_seconds = time.perf_counter() - started
        details = {"evolution_seconds": evolution_seconds,
                   "dense_materialization_seconds": materialization_seconds,
                   "peak_support": stats.peak_support, "peak_gate_index": stats.peak_gate_index,
                   "sparse_dictionary_entries": len(result),
                   "configured_estimated_memory_bytes": cap * sparse_backend.ESTIMATED_BYTES_PER_AMPLITUDE}
        return state, details
    if backend == "dense":
        import numpy as np
        from dense_statevector import evolve
        started = time.perf_counter()
        state = evolve(circuit.qubits, gates)
        return state, {"evolution_seconds": time.perf_counter() - started,
                       "representation": "complex128 dense NumPy array"}
    if backend == "qiskit":
        import numpy as np
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
        qc = QuantumCircuit(circuit.qubits)
        build_started = time.perf_counter()
        for gate in gates:
            op = gate[0]
            if op in ("h", "x", "z"):
                getattr(qc, op)(gate[1])
            elif op == "cx":
                qc.cx(gate[1], gate[2])
            elif op == "cp":
                qc.cp(float(gate[3]), gate[1], gate[2])
            else:
                getattr(qc, op)(float(gate[2]), gate[1])
        build_seconds = time.perf_counter() - build_started
        if len(qc.data) != len(expected_gates):
            raise AssertionError("Qiskit instruction count differs from canonical source")
        started = time.perf_counter()
        state = np.asarray(Statevector.from_instruction(qc).data, dtype=np.complex128)
        return state, {"circuit_build_seconds": build_seconds,
                       "statevector_evolution_seconds": time.perf_counter() - started,
                       "qiskit_version": importlib.metadata.version("qiskit"),
                       "qiskit_aer_used": False, "instruction_count": len(qc.data)}
    if backend == "cirq":
        import cirq
        import numpy as np
        qubits = cirq.LineQubit.range(circuit.qubits)
        qc = cirq.Circuit()
        build_started = time.perf_counter()
        for gate in gates:
            op = gate[0]
            if op in ("h", "x", "z"):
                operation = {"h": cirq.H, "x": cirq.X, "z": cirq.Z}[op](qubits[gate[1]])
            elif op == "cx":
                operation = cirq.CNOT(qubits[gate[1]], qubits[gate[2]])
            elif op == "cp":
                operation = cirq.CZPowGate(exponent=float(gate[3]) / math.pi)(qubits[gate[1]], qubits[gate[2]])
            else:
                operation = {"rx": cirq.rx, "ry": cirq.ry, "rz": cirq.rz}[op](float(gate[2]))(qubits[gate[1]])
            qc.append(operation, strategy=cirq.InsertStrategy.NEW)
        build_seconds = time.perf_counter() - build_started
        started = time.perf_counter()
        state = cirq.Simulator(dtype=np.complex128).simulate(qc, qubit_order=qubits[::-1]).final_state_vector
        return np.asarray(state, dtype=np.complex128), {
            "circuit_build_seconds": build_seconds,
            "statevector_evolution_seconds": time.perf_counter() - started,
            "cirq_core_version": importlib.metadata.version("cirq-core"),
            "instruction_count": sum(1 for _ in qc.all_operations()), "qubit_order": "reversed; q0 is LSB"}
    raise ValueError(f"unknown backend {backend}")


def implementation_digests():
    targets = {
        "runner": Path(__file__),
        "corpus_generator": ROOT / "validation" / "high_support" / "common.py",
        "dense_candidate": ROOT / "tools" / "high_support" / "dense_statevector.py",
        "sparse_backend": BENCH / "sparse_backend.py",
        "frontier_parser": BENCH / "frontier30.py",
        "quantum_frontend": BENCH / "quantum_frontend.py",
    }
    return {name: sha256(path.read_bytes()) for name, path in targets.items()}


def cpu_description():
    if os.name == "nt":
        for executable in ("powershell.exe", "powershell"):
            try:
                value = subprocess.check_output([executable, "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"],
                    text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
                if value:
                    return value
            except Exception:
                continue
    if platform.system() == "Linux":
        try:
            lines = Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines()
            values = {}
            for line in lines:
                if ":" not in line:
                    continue
                key, value = (part.strip() for part in line.split(":", 1))
                values.setdefault(key.lower(), value)
            for key in ("model name", "hardware", "model"):
                if values.get(key):
                    return values[key]
            implementer = values.get("cpu implementer")
            part = values.get("cpu part")
            if implementer or part:
                return f"{platform.machine()} CPU implementer {implementer or 'unknown'} part {part or 'unknown'}"
        except Exception:
            pass
    return platform.processor() or platform.machine()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--case", choices=("entangled", "random_connected", "connected_separable", "numerical_adversary", "roundtrip"), default="entangled")
    parser.add_argument("--backend", choices=("sparse", "dense", "qiskit", "cirq"), required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 5:
        parser.error("repeat must be in 1..5")
    plan = generate_plan(args.width, args.case)
    source_path = args.source_dir / f"{args.case}_{args.width}q.sbq"
    source = render_source(plan)
    if not source_path.exists() or source_path.read_bytes() != source:
        raise SystemExit(f"source corpus missing or differs from canonical rendering: {source_path}")
    circuit, parsed_source_hash = load_circuit(source_path)
    expected = gate_descriptors([tuple(g) for g in plan["gates"]])
    parsed = gate_descriptors(circuit.gates)
    plan_path = ROOT / "validation" / "high_support" / "plans" / f"{args.case}_{args.width}q.plan.json"
    plan_raw = plan_path.read_bytes()
    if json.loads(plan_raw) != dict(plan, source_sha256=sha256(source)):
        raise SystemExit("stored plan differs from deterministic generator/source")
    if parsed != expected or parsed_source_hash != sha256(source):
        raise SystemExit("source/parser/generator identity check failed")
    if len(circuit.gates) != len(expected):
        raise SystemExit("gate count mismatch")

    timings = []
    details_per_run = []
    final_state = None
    details = {}
    for _ in range(args.repeat):
        gc.collect()
        started = time.perf_counter()
        final_state, details = execute(args.backend, circuit, expected)
        timings.append(time.perf_counter() - started)
        details_per_run.append(details)
    import numpy as np
    state = np.ascontiguousarray(final_state, dtype=np.dtype("<c16"))
    norm = float(np.vdot(state, state).real)
    active = int(np.count_nonzero(np.abs(state) > 0.0))
    if not math.isfinite(norm):
        raise SystemExit("non-finite output norm")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.case}_{args.width}q_{args.backend}"
    vector_path = args.output_dir / f"{stem}.npy"
    np.save(vector_path, state, allow_pickle=False)
    vector_raw = vector_path.read_bytes()
    state_digest = sha256(state.tobytes(order="C"))
    report = {
        "schema": 1, "status": "PASS", "case": args.case, "backend": args.backend,
        "revision": revision(), "host": platform.platform(), "architecture": platform.machine(),
        "processor": cpu_description(), "python": platform.python_version(),
        "implementation_sha256": implementation_digests(), "plan_file_sha256": sha256(plan_raw),
        "source_name": source_path.name, "source_sha256": sha256(source),
        "source_bytes": len(source), "parsed_source_sha256": parsed_source_hash,
        "qubits": args.width, "gate_count": len(circuit.gates), "seed": plan["seed"],
        "gate_sequence_sha256": plan["gate_sequence_sha256"], "topology_kind": plan.get("topology_kind"),
        "two_qubit_edge_count": plan.get("two_qubit_edge_count"),
        "parsed_gate_sequence_sha256": sha256(canonical_json(parsed)),
        "basis_vector_length": len(state), "active_amplitudes_exact_nonzero": active,
        "norm": norm, "state_vector_sha256_little_endian_complex128": state_digest,
        "saved_npy_sha256": sha256(vector_raw), "saved_npy": vector_path.name,
        "elapsed_seconds": timings, "median_elapsed_seconds": float(np.median(timings)),
        "peak_rss_bytes_process_lifetime": peak_rss_bytes(), "backend_run_details": details_per_run,
        "limits": {"full_statevector": True, "shots": "not sampled", "hardware": "classical simulation"}}
    receipt_path = args.output_dir / f"{stem}.json"
    receipt_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "case": args.case, "backend": args.backend,
                      "qubits": args.width, "gates": len(circuit.gates), "active": active,
                      "norm": norm, "median_seconds": report["median_elapsed_seconds"],
                      "peak_rss_bytes": report["peak_rss_bytes_process_lifetime"],
                      "source_sha256": report["source_sha256"], "state_sha256": state_digest}))


if __name__ == "__main__":
    main()