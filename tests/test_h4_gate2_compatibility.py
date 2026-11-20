"""Research-only H4 Gate 2: demonstrate public v1 isolation and shared exact-subset semantics.

This suite deliberately does not introduce a public Hadamard certification route.
"""
from fractions import Fraction
import json
import unittest

from benchmarks.sb_quantum_benchmark.certified_support import (
    SEMANTICS as PUBLIC_SEMANTICS, certify, verify as verify_public,
)
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit
from tools.high_support.h3_format import encode
from tools.high_support.h4_ledger import (
    SCHEMA as RESEARCH_SCHEMA, generate, verify as verify_research,
)
from tools.high_support.h4_replay import value as binary64_rational


def research_source(qubits, gates, initial, budget="1"):
    """Create a bounded H4 input without using any floating-point gate arithmetic."""
    return json.dumps(
        {
            "qubits": qubits,
            "initial": encode(initial),
            "budget": budget,
            "gates": [[gate[0], list(gate[1:]), []] for gate in gates],
        },
        separators=(",", ":"),
    )


def h4_final_rationals(ledger):
    rows = ledger["steps"][-1]["post_bits"]
    return {
        basis: tuple(binary64_rational(int(word, 16)) for word in pair)
        for basis, pair in enumerate(rows)
    }


class Gate2Compatibility(unittest.TestCase):
    def test_signed_permutation_overlap_agrees_exactly_without_deletion(self):
        gates = (("x", 0), ("cx", 0, 1), ("z", 1), ("x", 1))
        initial = {0: complex(0.5, 0.25), 1: complex(0.125, -0.25)}
        circuit = Circuit(2, gates, "h4-v1-overlap")

        public = certify(circuit, initial, "1e-12", support_cap=4,
                         memory_budget_bytes=8192, interval=1)
        self.assertEqual(public["status"], "PASS")
        self.assertEqual(public["certificate"]["semantics"], PUBLIC_SEMANTICS)
        self.assertEqual(public["certificate"]["ledger"]["events"], [])
        self.assertEqual(verify_public(circuit, initial, public["state"],
                                       public["certificate"], "1e-12")["status"], "PASS")

        source = research_source(2, gates, initial)
        h4 = generate(source)
        self.assertEqual(h4["schema"], RESEARCH_SCHEMA)
        self.assertEqual(h4["decision"], "PASS")
        self.assertEqual(verify_research(source, h4), "PASS")
        self.assertEqual(len(h4["steps"]), len(gates))

        # Equality here means exact mathematical values, not equality of zero-sign bits
        # or interchangeability of public v1 and experimental H4 receipt schemas.
        h4_values = h4_final_rationals(h4)
        for basis in range(4):
            actual = public["state"].get(basis, 0j)
            self.assertEqual(
                (Fraction(actual.real), Fraction(actual.imag)),
                h4_values[basis],
                f"basis {basis} differed between signed-permutation engines",
            )

    def test_hadamard_research_pass_does_not_enable_public_certification(self):
        gates = (("h", 0),)
        initial = {0: 1+0j}
        source = research_source(1, gates, initial)
        h4 = generate(source)
        self.assertEqual(h4["decision"], "PASS")
        self.assertEqual(verify_research(source, h4), "PASS")

        circuit = Circuit(1, gates, "hadamard-research-only")
        result = certify(circuit, initial, "1e-6", support_cap=2,
                         memory_budget_bytes=4096)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertIn("h", result["reason"])

        # Inserting a research ledger into the versioned public certificate contract
        # must never yield a valid v1 certification.
        self.assertNotEqual(
            verify_public(circuit, initial, {0: 1+0j}, h4, "1e-6")["status"],
            "PASS",
        )
        self.assertNotEqual(RESEARCH_SCHEMA, PUBLIC_SEMANTICS)

    def test_budget_normalization_and_gate_contracts_stay_distinct(self):
        initial = {0: 0.5+0j}
        circuit = Circuit(1, (("x", 0),))
        self.assertEqual(
            certify(circuit, initial, "1e-6", support_cap=2,
                    memory_budget_bytes=4096, normalize=True)["status"],
            "UNSUPPORTED",
        )
        with self.assertRaises(ValueError):
            certify(circuit, initial, "1", support_cap=2,
                    memory_budget_bytes=4096)

        # The standalone research source intentionally supports an integer
        # absolute budget of "1"; that is not a reason to widen the public API.
        source = research_source(1, (("h", 0),), initial, budget="1")
        self.assertEqual(verify_research(source, generate(source)), "PASS")


if __name__ == "__main__":
    unittest.main()
