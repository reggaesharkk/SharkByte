from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.high_support import h4_compatibility as c
from tools.high_support import h4_historical_checkout as history

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT/"evidence/h4-candidate"


def raw(obj):
    return (c.canonical(obj)+"\n").encode("ascii")


def request(gates, *, negative=False, budget="1"):
    return raw({"contract": c.VERSION, "qubits": 2, "gates": gates, "budget": budget,
                "initial": [[0,"3ff0000000000000","8000000000000000" if negative else "0"*16],
                            [1,"3ff0000000000000","0000000000000001"]]})


class Compatibility(unittest.TestCase):
    def test_pinned_archival_baseline(self):
        source, receipt = (ARCHIVE/name for name in ("source.json","receipt.json"))
        self.assertEqual(history.verify(source, receipt), ("VERIFIED_PASS",0))
        result = c.compare(c.VERSION,source.read_bytes(),receipt.read_bytes(),
                           c.VERSION,source.read_bytes(),receipt.read_bytes())
        for key in ("syntax","mathematical","bit_level","certificate"):
            self.assertEqual(result[key],"PASS")
        self.assertEqual(result["execution_authenticity"],"UNAUTHENTICATED")

    def test_historical_generation_and_independent_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history.extract_pinned(history.historical_archive(),root)
            candidates = [("original", (ARCHIVE/"source.json").read_bytes()),
                          ("mixed",request([["h",[0]],["h",[0]],["cx",[0,1]],
                                            ["z",[1]],["x",[0]],["h",[1]]], negative=True)),
                          ("over",request([["h",[0]]], budget="0"))]
            for name, source in candidates:
                src, cert = root/(name+".source"), root/(name+".receipt")
                src.write_bytes(source)
                flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
                proc = subprocess.run([sys.executable,"-B",*flags,"-m",
                                       "tools.high_support.h4_candidate","generate",
                                       str(src),str(cert)], cwd=root,env=history.historical_environment(),
                                      capture_output=True,text=True,timeout=65)
                outcome = "VERIFIED_BUDGET_EXCEEDED" if name == "over" else "VERIFIED_PASS"
                self.assertEqual((proc.returncode,proc.stdout.strip()),
                                 (int(name == "over"),outcome),proc.stderr)
                if name == "original":
                    self.assertEqual(cert.read_bytes(),(ARCHIVE/"receipt.json").read_bytes())
                trace = c.verify(c.VERSION,source,cert.read_bytes())
                self.assertEqual(trace.outcome,outcome)
                self.assertEqual(c.compare_traces(trace,trace)["accuracy"],[outcome,outcome])
                self.assertEqual(c.compare_traces(trace,trace)["within_budget_certified"],
                                 [name != "over"]*2)

    def test_category_distinctions(self):
        trace,_ = c.reconstruct(request([["x",[0]]]))
        zeros,_ = c.reconstruct(request([["x",[0]]],negative=True))
        result = c.compare_traces(trace,zeros)
        self.assertEqual(result["mathematical"],"PASS")
        self.assertEqual(result["bit_level"],"NOT_ESTABLISHED")
        self.assertTrue(result["final_mathematical_state_equal"])
        # Synthetic contract changes, never accepted by the version dispatcher.
        for field, value in (("arithmetic","synthetic rounding"),("normalization","synthetic normalization"),
                             ("budget",Fraction(2)),("outcome","VERIFIED_BUDGET_EXCEEDED")):
            result = c.compare_traces(trace,replace(trace,**{field:value}))
            self.assertTrue(result["observed_words_equal"])
            self.assertNotEqual(result["decision"],"COMPATIBLE")
        a,_ = c.reconstruct(request([["x",[0]],["z",[1]]]))
        b,_ = c.reconstruct(request([["z",[1]],["x",[0]]]))
        result = c.compare_traces(a,b)
        self.assertTrue(result["final_mathematical_state_equal"])
        self.assertEqual(result["mathematical"],"DIFFERENT_OR_UNPROVED")

    def test_forgery_and_canonical_refusal(self):
        src = (ARCHIVE/"source.json").read_bytes()
        cert = (ARCHIVE/"receipt.json").read_bytes()
        for field in ("contract","candidate_sha256","source_sha256","outcome"):
            with self.assertRaises(ValueError):
                c.verify(c.VERSION,src,raw(dict(json.loads(cert),**{field:"forged"})))
        for key, value in (("arithmetic","0"),("total","0"),("deletion","1")):
            record = json.loads(cert)
            record["ledger"]["steps"][0][key] = value
            with self.assertRaises(ValueError):
                c.verify(c.VERSION,src,raw(record))
        for bad in (cert.rstrip(),cert.replace(b'{"candidate_sha256":',b'{"contract":0,"candidate_sha256":')):
            with self.assertRaises(ValueError):
                c.verify(c.VERSION,src,bad)
        with self.assertRaises(c.Unsupported):
            c.verify("candidate-v2",src,cert)

    def test_missing_or_modified_pinned_source(self):
        src, cert = ((ARCHIVE/name).read_bytes() for name in ("source.json","receipt.json"))
        with patch.object(history,"historical_archive",side_effect=history.HistoryUnavailable("missing")):
            with self.assertRaises(history.HistoryUnavailable):
                c.compare(c.VERSION,src,cert,c.VERSION,src,cert)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            history.extract_pinned(history.historical_archive(),root)
            path = root/"tools/high_support/h4_replay.py"
            path.write_bytes(path.read_bytes()+b"\n# modified\n")
            with self.assertRaisesRegex(ValueError,"tree content mismatch"):
                history.validate_snapshot(root)
            path.unlink()
            with self.assertRaises(FileNotFoundError):
                history.validate_snapshot(root)

    def test_rounding_edges(self):
        self.assertEqual(c.rounded(-Fraction(1,2**1075)),c.SIGN)
        self.assertEqual(c.rounded(Fraction(3,2**1075)),2)
        self.assertEqual(c.rounded(Fraction((1<<53)-1,2**1075)),1<<52)
        with self.assertRaisesRegex(ValueError,"overflow"):
            c.rounded(c.fraction(0x7fefffffffffffff)+2**970)
