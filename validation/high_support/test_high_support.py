"""Regression tests for the new high-support experiment machinery."""
from __future__ import annotations
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
BENCH=ROOT/"benchmarks"/"sb_quantum_benchmark"
for path in (ROOT,BENCH,ROOT/"tools"/"high_support"):
    if str(path) not in sys.path: sys.path.insert(0,str(path))
from validation.high_support.common import (WIDTHS, analytic_phase_matrix, entanglement_metrics,
    gate_descriptors, generate_plan, is_two_qubit_graph_connected, render_source, sha256)
from frontier30 import load_circuit
from sparse_backend import Circuit, evolve as sparse_evolve
from dense_statevector import evolve as dense_evolve
import numpy as np


class HighSupportCorpusTests(unittest.TestCase):
    def test_checked_in_sources_match_deterministic_plans_and_parser(self):
        cases=(("entangled",WIDTHS),("random_connected",WIDTHS),
               ("connected_separable",(20,)),("numerical_adversary",(17,)),
               ("roundtrip",(17,18)))
        for case,widths in cases:
            for width in widths:
                with self.subTest(case=case,width=width):
                    plan=generate_plan(width,case)
                    source=ROOT/"examples"/"high_support"/f"{case}_{width}q.sbq"
                    data=source.read_bytes()
                    self.assertEqual(data,render_source(plan))
                    parsed,digest=load_circuit(source)
                    self.assertEqual(digest,sha256(data))
                    self.assertEqual(parsed.qubits,width)
                    self.assertEqual(gate_descriptors(parsed.gates),gate_descriptors(plan["gates"]))
                    stored=ROOT/"validation"/"high_support"/"plans"/f"{case}_{width}q.plan.json"
                    import json
                    payload=json.loads(stored.read_text(encoding="utf-8"))
                    self.assertEqual(payload,dict(plan,source_sha256=digest))
                    self.assertTrue(is_two_qubit_graph_connected(plan))

    def test_seeded_random_topology_is_repeatable_and_not_complete(self):
        plan=generate_plan(20,"random_connected")
        self.assertEqual(plan,generate_plan(20,"random_connected"))
        self.assertIn("seeded_erdos_renyi",plan["topology_kind"])
        all_cross_edges=(20//2)*(20-20//2)
        self.assertLess(len(plan["cross_cut_cp"]),all_cross_edges)
        self.assertGreater(len(plan["cross_cut_cp"]),20)
        self.assertTrue(is_two_qubit_graph_connected(plan))

    def test_dense_candidate_matches_sparse_backend_on_supported_gates(self):
        gates=(
            ("h",0),("h",2),("cp",0,3,0.732),("cx",2,1),
            ("rx",1,-0.417),("ry",3,1.129),("rz",0,-2.91),
            ("h",2),("cp",1,3,-0.618),
        )
        circuit=Circuit(4,gates,"dense-candidate-test")
        sparse=sparse_evolve(circuit,support_cap=16,memory_budget_bytes=16*512,max_seconds=5)
        expected=np.asarray([sparse.get(i,0j) for i in range(16)],dtype=np.complex128)
        actual=dense_evolve(4,gates)
        overlap=np.vdot(expected,actual)
        actual*=np.conjugate(overlap/abs(overlap))
        self.assertLess(float(np.max(np.abs(expected-actual))),2e-12)
        self.assertAlmostEqual(float(np.vdot(actual,actual).real),1.0,places=12)

    def test_connected_cnot_control_is_product_state_despite_dense_support(self):
        width=5
        gates=tuple(("h",q) for q in range(width))+tuple(("cx",q,q+1) for q in range(width-1))
        plan={"qubits":width,"gates":gates}
        self.assertTrue(is_two_qubit_graph_connected(plan))
        state=dense_evolve(width,gates)
        expected=np.full(1<<width,1/math.sqrt(1<<width),dtype=np.complex128)
        self.assertLess(float(np.max(np.abs(state-expected))),1e-14)
        metrics=entanglement_metrics(state,width,width//2)
        self.assertEqual(metrics["schmidt_rank_at_relative_cutoff"],1)
        self.assertAlmostEqual(metrics["purity"],1.0,places=12)

    def test_analytic_random_phase_matrix_is_high_rank(self):
        plan=generate_plan(17,"random_connected")
        matrix=analytic_phase_matrix(plan)
        metrics=entanglement_metrics(matrix.T.reshape(-1),17,plan["split"])
        self.assertEqual(metrics["schmidt_rank_at_relative_cutoff"],1<<plan["split"])
        self.assertGreater(metrics["entropy_fraction_of_maximum"],0.75)

    def test_near_4pi_adversary_stays_inside_supported_angle_bound(self):
        plan=generate_plan(17,"numerical_adversary")
        angle_limit=4*math.pi
        angles=[abs(g[3] if g[0]=="cp" else g[2]) for g in plan["gates"] if g[0] in ("cp","rx","ry","rz")]
        self.assertTrue(angles)
        self.assertLessEqual(max(angles),angle_limit)
        self.assertEqual(max(angles),angle_limit)
        self.assertTrue(is_two_qubit_graph_connected(plan))

    def test_roundtrip_gate_sequence_is_exact_inverse_in_reverse_order(self):
        plan=generate_plan(17,"roundtrip")
        count=plan["forward_gate_count"]
        forward=plan["gates"][:count]
        inverse=plan["gates"][count:]
        self.assertEqual(len(inverse),count)
        for gate,rev in zip(reversed(forward),inverse):
            op=gate[0]
            expected=list(gate)
            if op=="cp": expected[3]=-float(expected[3])
            elif op in ("rx","ry","rz"): expected[2]=-float(expected[2])
            self.assertEqual(list(rev),expected)


if __name__=="__main__":
    unittest.main()