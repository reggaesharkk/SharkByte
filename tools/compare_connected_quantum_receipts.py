"""Directly compare independently saved Qiskit and Cirq connected-circuit vectors."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


AMPLITUDE_TOLERANCE = 1e-10
PROBABILITY_MAX_TOLERANCE = 1e-10
PROBABILITY_L1_TOLERANCE = 1e-9
NORMALIZATION_TOLERANCE = 1e-10


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _read_receipt(path: Path) -> tuple[dict, dict[str, np.ndarray]]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    claimed = receipt.get("receipt_sha256")
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if claimed != _sha256(_canonical(unsigned)):
        raise ValueError(f"receipt hash mismatch: {path}")
    archive_info = receipt["state_archive"]
    archive = path.parent / archive_info["file"]
    if _sha256(archive.read_bytes()) != archive_info["sha256"]:
        raise ValueError(f"state archive hash mismatch: {archive}")
    with np.load(archive, allow_pickle=False) as opened:
        vectors = {key: np.asarray(opened[key], dtype="<c16") for key in opened.files}
    if len(vectors) != archive_info["vectors"]:
        raise ValueError(f"state vector count mismatch: {archive}")
    return receipt, vectors


def _compare(reference: np.ndarray, other: np.ndarray) -> dict:
    if reference.shape != other.shape:
        return {"status": "FAIL", "reason": "statevector shape mismatch"}
    overlap = np.vdot(reference, other)
    phase = overlap / abs(overlap) if abs(overlap) else 1.0 + 0.0j
    aligned = other * np.conjugate(phase)
    p_ref = np.abs(reference) ** 2
    p_other = np.abs(other) ** 2
    max_amplitude = float(np.max(np.abs(reference - aligned), initial=0.0))
    max_probability = float(np.max(np.abs(p_ref - p_other), initial=0.0))
    l1_probability = float(np.sum(np.abs(p_ref - p_other), dtype=np.float64))
    norm = math.fsum(float(value) for value in p_other)
    passed = (
        max_amplitude <= AMPLITUDE_TOLERANCE
        and max_probability <= PROBABILITY_MAX_TOLERANCE
        and l1_probability <= PROBABILITY_L1_TOLERANCE
        and abs(norm - 1.0) <= NORMALIZATION_TOLERANCE
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "basis_states_compared": int(reference.size),
        "global_phase_radians": float(math.atan2(float(phase.imag), float(phase.real))),
        "max_complex_amplitude_error_global_phase_aligned": max_amplitude,
        "max_probability_error": max_probability,
        "l1_probability_error": l1_probability,
        "cirq_norm": norm,
        "cirq_norm_error": abs(norm - 1.0),
    }


def _entanglement_witnesses(state: np.ndarray, width: int) -> dict[str, dict]:
    """Check cut purity independently from the SVD witness in each run receipt."""
    cuts = {
        "lower_half_vs_upper_half": list(range(max(1, width // 2))),
        "even_qubits_vs_odd_qubits": list(range(0, width, 2)),
        "q0_vs_rest": [0],
    }
    if width >= 4:
        cuts["outer_qubits_vs_middle"] = [0, width - 1]
    tensor = state.reshape((2,) * width)
    result = {}
    for name, subset in cuts.items():
        subset = sorted(set(subset))
        complement = [q for q in range(width) if q not in subset]
        matrix = np.transpose(
            tensor, [width - 1 - q for q in complement]
            + [width - 1 - q for q in subset]
        ).reshape(1 << len(complement), 1 << len(subset))
        norm = float(np.vdot(matrix, matrix).real)
        if not math.isfinite(norm) or abs(norm - 1.0) > NORMALIZATION_TOLERANCE:
            raise ValueError(f"{name}: state is not normalized before partial trace")
        if matrix.shape[0] <= matrix.shape[1]:
            reduced = matrix @ matrix.conjugate().T
        else:
            reduced = matrix.conjugate().T @ matrix
        purity = float(np.trace(reduced @ reduced).real)
        result[name] = {
            "reduced_state_purity": purity,
            "entangled_across_cut": purity < 1.0 - 1e-8,
            "reduced_dimension": int(reduced.shape[0]),
            "normalization": norm,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qiskit_receipt", type=Path)
    parser.add_argument("cirq_receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    qiskit, qiskit_vectors = _read_receipt(args.qiskit_receipt.resolve())
    cirq, cirq_vectors = _read_receipt(args.cirq_receipt.resolve())
    if (qiskit["status"], cirq["status"]) != ("PASS", "PASS"):
        raise ValueError("Both backend receipts must pass before cross-comparison")
    if (qiskit["backend"], cirq["backend"]) != ("qiskit", "cirq"):
        raise ValueError("Expected one Qiskit receipt and one Cirq receipt")
    for key in ("corpus_sha256", "corpus_cases", "code_sha256"):
        if qiskit[key] != cirq[key]:
            raise ValueError(f"backend receipts disagree on {key}")

    qiskit_cases = {case["id"]: case for case in qiskit["cases"]}
    cirq_cases = {case["id"]: case for case in cirq["cases"]}
    if qiskit_cases.keys() != cirq_cases.keys():
        raise ValueError("backend receipts contain different circuit IDs")

    rows = []
    for case_id in qiskit_cases:
        qcase = qiskit_cases[case_id]
        ccase = cirq_cases[case_id]
        if (qcase["source_sha256"], qcase["source"]) != (
            ccase["source_sha256"], ccase["source"]
        ):
            raise ValueError(f"{case_id}: exact source identity differs")
        if qcase["entanglement_expectation"] != ccase["entanglement_expectation"]:
            raise ValueError(f"{case_id}: entanglement control classification differs")
        phases = {}
        for phase_name, ref_section in (
            ("prefix", "prefix_reference"),
            ("inverse", "inverse_reference"),
        ):
            key = case_id + ("__prefix" if phase_name == "prefix" else "__inverse")
            qvec = qiskit_vectors[key]
            cvec = cirq_vectors[key]
            if _sha256(np.ascontiguousarray(qvec, dtype="<c16").tobytes()) != (
                qcase[ref_section]["state_sha256"]
            ):
                raise ValueError(f"{case_id}/{phase_name}: Qiskit vector hash mismatch")
            if _sha256(np.ascontiguousarray(cvec, dtype="<c16").tobytes()) != (
                ccase[ref_section]["state_sha256"]
            ):
                raise ValueError(f"{case_id}/{phase_name}: Cirq vector hash mismatch")
            phases[phase_name] = _compare(qvec, cvec)
        q_entanglement = _entanglement_witnesses(qiskit_vectors[case_id + "__prefix"],
                                                 qcase["width"])
        c_entanglement = _entanglement_witnesses(cirq_vectors[case_id + "__prefix"],
                                                  ccase["width"])
        q_svd = qcase["prefix_entanglement"]["witnesses"]
        c_svd = ccase["prefix_entanglement"]["witnesses"]
        expectation = qcase["entanglement_expectation"]
        entanglement_ok = (
            q_entanglement.keys() == c_entanglement.keys()
            == q_svd.keys() == c_svd.keys()
        )
        if entanglement_ok:
            entanglement_ok = all(
                q_entanglement[name]["entangled_across_cut"]
                == c_entanglement[name]["entangled_across_cut"]
                and abs(q_entanglement[name]["reduced_state_purity"]
                        - c_entanglement[name]["reduced_state_purity"]) <= 1e-10
                and abs(q_entanglement[name]["reduced_state_purity"]
                        - q_svd[name]["reduced_state_purity"]) <= 1e-10
                and abs(c_entanglement[name]["reduced_state_purity"]
                        - c_svd[name]["reduced_state_purity"]) <= 1e-10
                for name in q_entanglement
            )
        if expectation == "nonfactorizing-across-tested-cuts":
            entanglement_ok = entanglement_ok and all(
                item["entangled_across_cut"] for item in q_entanglement.values()
            )
        elif expectation == "separable-product-control":
            entanglement_ok = entanglement_ok and all(
                not item["entangled_across_cut"]
                and abs(item["reduced_state_purity"] - 1.0) <= 1e-10
                for item in q_entanglement.values()
            )
        phases_passed = all(item["status"] == "PASS" for item in phases.values())
        row_status = "PASS" if phases_passed and entanglement_ok else "FAIL"
        rows.append({
            "id": case_id,
            "width": qcase["width"],
            "source_sha256": qcase["source_sha256"],
            "prefix": phases["prefix"],
            "inverse": phases["inverse"],
            "entanglement_expectation": expectation,
            "qiskit_entanglement_witnesses": q_entanglement,
            "cirq_entanglement_witnesses": c_entanglement,
            "entanglement_crosscheck_status": "PASS" if entanglement_ok else "FAIL",
            "status": row_status,
        })

    failures = [row["id"] for row in rows if row["status"] != "PASS"]
    report = {
        "schema": 1,
        "status": "PASS" if not failures else "FAIL",
        "corpus_sha256": qiskit["corpus_sha256"],
        "corpus_cases": len(rows),
        "qiskit_version": qiskit["reference_library_version"],
        "cirq_core_version": cirq["reference_library_version"],
        "numpy_qiskit_version": qiskit["numpy_version"],
        "numpy_cirq_version": cirq["numpy_version"],
        "entanglement_crosscheck_method": (
            "Independent reduced-density-matrix purity from matrix products; "
            "run receipts compute Schmidt spectra by SVD."
        ),
        "comparator_sha256": _sha256(Path(__file__).read_bytes()),
        "windows_arm64_qiskit_host": qiskit["host"],
        "windows_arm64_cirq_host": cirq["host"],
        "failed_cases": failures,
        "cases": rows,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"Refusing to overwrite existing report: {output}")
    report["report_sha256"] = _sha256(_canonical(report))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(f"{report['status']}: Qiskit/Cirq direct comparison {len(rows) - len(failures)}/{len(rows)}")
    print(f"Report: {output}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
