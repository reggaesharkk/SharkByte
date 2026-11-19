import copy
import hashlib
import json
import math
import random
import unittest
from fractions import Fraction
from pathlib import Path

from benchmarks.sb_quantum_benchmark.certified_support import certify, verify
from benchmarks.sb_quantum_benchmark.sparse_backend import Circuit
from benchmarks.sb_quantum_benchmark.bounded_support import simulate


class CertifiedSupportTests(unittest.TestCase):
    def make(self, gates, initial, budget="1e-8", protected=()):
        circuit = Circuit(12, tuple(gates), "test")
        return circuit, certify(circuit, initial, budget, support_cap=64,
                                memory_budget_bytes=64*2048, interval=1,
                                protected=protected)

    def test_default_compactor_behavior_unchanged(self):
        state, ledger = simulate(Circuit(1, (("x", 0),)), "1e-8",
                                 support_cap=2, memory_budget_bytes=1024)
        self.assertEqual(state, {1: 1+0j})
        self.assertFalse(ledger["events"])

    def test_exact_gate_and_deletion_certificate(self):
        circuit, result = self.make(
            [("x",0),("z",0),("cx",0,3),("cx",0,3),("x",0)],
            {0:0.75+0.25j, 1:complex(math.ldexp(1.0,-40),-math.ldexp(1.0,-41))})
        self.assertEqual(result["status"],"PASS")
        verified = verify(circuit,
            {0:0.75+0.25j, 1:complex(math.ldexp(1.0,-40),-math.ldexp(1.0,-41))},
            result["state"],result["certificate"],"1e-8")
        self.assertEqual(verified["status"],"PASS")
        self.assertEqual(verified["coefficient_evaluation_error"],"0")
        self.assertEqual(verified["complex_gate_arithmetic_error"],"0")
        self.assertEqual(verified["accumulated_gate_error"],"0")
        self.assertEqual(verified["renormalization_error"],"0")
        self.assertGreaterEqual(Fraction(verified["certified_l2_bound"])**2,
                                Fraction(verified["exact_squared_error"]))

    def test_subnormal_exact_mass(self):
        tiny = math.ulp(0.0)
        initial = {0:1+0j, 1:complex(tiny,0)}
        circuit, result = self.make([("cx",0,1),("x",0),("z",1)],initial,"1e-320")
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["verification"]["status"],"PASS")
        event = result["certificate"]["ledger"]["events"][0]
        self.assertTrue(event["removed"])
        self.assertEqual(event["removed"][0][1],tiny.hex())
        self.assertEqual(result["certificate"]["error_components"]["coefficient_evaluation"],"0")

    def test_protection_is_a_fixed_basis_coordinate(self):
        circuit=Circuit(3,(("x",0),),"moving-protected-branch")
        initial={2:1+0j,1:complex(1e-7,0)}
        result=certify(circuit,initial,"1e-6",support_cap=4,
                       memory_budget_bytes=8192,protected=(1,))
        self.assertEqual(result["status"],"PASS")
        # X(0) moves the small branch from protected index 1 to index 0.
        # The fixed protection set does not follow it, so the ledger may delete it.
        self.assertIn(0,[item[0] for event in result["certificate"]["ledger"]["events"]
                         for item in event["removed"]])
        self.assertNotIn(0,result["state"])
        self.assertIn(1,result["certificate"]["ledger"]["protected"])

    def test_supported_gate_fuzz_against_independent_reference(self):
        for width in (2,4,7,12):
            for seed in (0,3):
                rng = random.Random(width*100+seed)
                gates = []
                for _ in range(80):
                    op = rng.choice(("x","z","cx"))
                    if op == "cx":
                        a,b = rng.sample(range(width),2)
                        gates.append((op,a,b))
                    else:
                        gates.append((op,rng.randrange(width)))
                initial = {0:complex(.625,-.125), 1:complex(-.375,.25),
                           (1<<width)-1:complex(math.ldexp(1.0,-300),-math.ldexp(1.0,-280))}
                circuit = Circuit(width,tuple(gates))
                for budget in ("1e-12","0.001"):
                    result = certify(circuit,initial,budget,support_cap=16,
                                     memory_budget_bytes=16*2048,interval=7)
                    self.assertEqual(result["status"],"PASS")
                    exact = {k:(Fraction(v.real),Fraction(v.imag)) for k,v in initial.items()}
                    for gate in gates:
                        op=gate[0]
                        if op=="x":
                            bit=1<<gate[1]
                            exact={k^bit:v for k,v in exact.items()}
                        elif op=="cx":
                            c,t=1<<gate[1],1<<gate[2]
                            exact={k^t if k&c else k:v for k,v in exact.items()}
                        else:
                            bit=1<<gate[1]
                            exact={k:((-v[0],-v[1]) if k&bit else v) for k,v in exact.items()}
                    verification=verify(circuit,initial,result["state"],result["certificate"],budget)
                    self.assertEqual(verification["status"],"PASS")
                    self.assertGreaterEqual(Fraction(verification["certified_l2_bound"])**2,
                                            Fraction(verification["exact_squared_error"]))

    def test_mixing_and_angle_gates_are_explicitly_unsupported(self):
        for gate in (("h",0),("rx",0,.1),("ry",0,1e-300),("rz",0,0.0),("cp",0,1,0.0)):
            circuit=Circuit(2,(gate,) if gate[0]!="cp" else (gate,))
            result=certify(circuit,{0:1+0j,1:1e-20+0j},"1e-8",
                           support_cap=4,memory_budget_bytes=8192)
            self.assertEqual(result["status"],"UNSUPPORTED")
            self.assertIn(gate[0],result["reason"])

    def test_normalization_is_explicitly_unsupported(self):
        result=certify(Circuit(1,(("x",0),)),{0:.5+0j},"1e-6",
                       support_cap=2,memory_budget_bytes=1024,normalize=True)
        self.assertEqual(result["status"],"UNSUPPORTED")
        self.assertIn("renormalized",result["reason"])

    def test_adversarial_cancellation_and_interference_unsupported(self):
        cancellation=Circuit(2,(("h",0),("h",0),("h",0),("h",0)))
        interference=Circuit(3,(("h",0),("cx",0,1),("h",0),("cx",0,1)))
        for circuit in (cancellation,interference):
            result=certify(circuit,{0:1+0j},"1e-8",support_cap=8,memory_budget_bytes=4096)
            self.assertEqual(result["status"],"UNSUPPORTED")

    def test_forged_event_witnesses_and_schedule(self):
        initial={0:1+0j,1:complex(2e-5,0),2:complex(3e-5,-1e-5)}
        circuit=Circuit(4,(("cx",0,1),("cx",1,0)))
        result=certify(circuit,initial,"1e-4",support_cap=8,
                       memory_budget_bytes=16384,interval=1,protected=(2,))
        self.assertEqual(len(result["certificate"]["ledger"]["events"]),2)
        mutations=(
            lambda c:c["ledger"]["events"].reverse(),
            lambda c:c["ledger"]["events"][0]["removed"].append(
                c["ledger"]["events"][0]["removed"][0]),
            lambda c:c["ledger"]["events"][0]["removed"][0].__setitem__(1,"0x1.0p-20"),
            lambda c:c["ledger"]["events"][0].__setitem__("ticks",1),
            lambda c:c["ledger"]["events"][1].__setitem__("after_gate",1),
            lambda c:c["ledger"].__setitem__("budget","1/9999"),
        )
        for mutate in mutations:
            bad=copy.deepcopy(result["certificate"])
            mutate(bad)
            self.assertEqual(verify(circuit,initial,result["state"],bad,"1e-4")["status"],"FAIL")

    def test_unsupported_environment_is_explicit(self):
        from unittest.mock import patch
        import benchmarks.sb_quantum_benchmark.certified_support as module
        with patch.object(module,"_environment_reason",return_value="test runtime lacks binary64"):
            result=certify(Circuit(1,(("x",0),)),{0:1+0j},"1e-8",
                           support_cap=2,memory_budget_bytes=1024)
        self.assertEqual(result,dict(status="UNSUPPORTED",reason="test runtime lacks binary64"))

    def test_forged_certificate_and_input_binding(self):
        initial={0:.5+.25j,1:complex(math.ldexp(1.,-20),0)}
        circuit=Circuit(2,(("x",0),("z",1)))
        result=certify(circuit,initial,"1e-8",support_cap=4,memory_budget_bytes=2048)
        cert=copy.deepcopy(result["certificate"])
        cert["error_components"]["accumulated_gate_error"]="1/100"
        self.assertEqual(verify(circuit,initial,result["state"],cert,"1e-8")["status"],"FAIL")
        self.assertEqual(verify(circuit,{0:.5+.25j,1:complex(math.ldexp(1.,-19),0)},
                                result["state"],result["certificate"],"1e-8")["status"],"FAIL")

    def test_existing_48_configurations_explicitly_unsupported(self):
        evidence=json.loads((Path(__file__).resolve().parents[1]/
                             "evidence/bounded-audit.json").read_text())
        self.assertEqual(len(evidence["fuzz"]),48)
        for width in (2,4,7):
            for seed in range(4):
                rng=random.Random(seed+100*width)
                gates=[]
                for _ in range(5):
                    for op in ("ry","h","rx","cx","cp","x","rz","z"):
                        a,b=rng.sample(range(width),2)
                        angle=rng.choice([1e-6,-1e-4,.31,-1.17])
                        gates.append((op,a,b) if op=="cx" else
                                     (op,a,b,angle) if op=="cp" else
                                     (op,a,angle) if op in ("rx","ry","rz") else (op,a))
                digest=hashlib.sha256(json.dumps(gates,separators=(",",":")).encode()).hexdigest()
                matching=[r for r in evidence["fuzz"] if r["width"]==width and r["seed"]==seed]
                self.assertEqual(len(matching),4)
                self.assertTrue(all(r["gates_sha256"]==digest for r in matching))
                result=certify(Circuit(width,tuple(gates)),{0:1+0j},"1e-8",
                               support_cap=1<<width,memory_budget_bytes=(1<<width)*2048)
                self.assertEqual(result["status"],"UNSUPPORTED")
