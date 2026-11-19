import math
import unittest
from decimal import Decimal
from pathlib import Path

from benchmarks.sb_quantum_benchmark.frontier30 import Circuit, load_circuit, simplify_inverses


class InverseTests(unittest.TestCase):
    def test_adversarial(self):
        for gates in [
            (("cx", 0, 1), ("cx", 1, 0)),
            (("rx", 0, 1.), ("rx", 0, math.nextafter(-1., 0.))),
            (("ry", 0, 1e-100),),
            (("h", 0), ("z", 0), ("h", 0)),
            (("rz", 0, 1.), ("rx", 0, -1.)),
        ]:
            circuit = Circuit(2, gates)
            self.assertEqual(simplify_inverses(circuit), (circuit, []))

    def test_roundtrip_source(self):
        path = Path(__file__).resolve().parents[1] / "examples/high_support/roundtrip_17q.sbq"
        gates = [line.strip().rstrip(";").split() for line in path.read_text().splitlines()[4:-2]]
        self.assertEqual(len(gates), 214)
        for left, right in zip(gates[:107], reversed(gates[107:])):
            self.assertEqual(left[0], right[0])
            if left[0] in ("cx", "h"):
                self.assertEqual(left, right)
            else:
                self.assertIn(left[0], ("cp", "rx", "ry", "rz"))
                self.assertEqual(left[2:], right[2:])
                self.assertEqual(Decimal(left[1]), Decimal(right[1]).copy_negate())
        reduced, pairs = simplify_inverses(load_circuit(path)[0])
        self.assertEqual(reduced.gates, ())
        self.assertEqual(pairs, [(106-i, 107+i) for i in range(107)])
