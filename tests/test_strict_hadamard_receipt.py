import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.high_support.h3_format import digest
from tools.high_support.h3_generate import generate
from tools.high_support.h3_verify import verify as legacy_math
from tools.high_support.h4_ledger import strict_json, verify as h4_math
from tools.high_support.strict_hadamard_receipt import seal, validate, verify

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"evidence/h3/circuit.json"


def archive(family, host="windows-arm64"):
    return json.loads((ROOT/"evidence"/family/(host+".json")).read_text(encoding="utf-8"))


def resize(receipt):
    receipt["ledger_bytes"] = len(json.dumps(receipt["ledger"], indent=2).encode())


class StrictReceipt(unittest.TestCase):
    def test_archives_and_legacy_zero_gap(self):
        source = SOURCE.read_text(encoding="utf-8")
        for host in ("windows-arm64", "ubuntu-wsl2-arm64"):
            for family, bits in (("h3", "RECORDED_ONLY"), ("h4-gate1", "DETERMINISTIC_REPLAY")):
                result = verify(source, seal(source, archive(family, host)))
                self.assertEqual(result["bit_replay"], bits)
                self.assertEqual(result["execution_provenance"], "UNAUTHENTICATED")
        altered = archive("h3")
        post = altered["ledger"]["steps"][0]["post"]
        post.append([7, "0"*16, "8000000000000000"])
        resize(altered)
        self.assertEqual(legacy_math(source, altered["ledger"]), "PASS")
        with self.assertRaisesRegex(ValueError, "noncanonical"):
            validate(source, altered)

    def test_order_duplicates_missing_and_bit_forgery(self):
        source = SOURCE.read_text()
        for mutation in (lambda p: p.reverse(), lambda p: p.append(p[0]), lambda p: p.pop()):
            receipt = archive("h3")
            mutation(receipt["ledger"]["steps"][0]["post"])
            resize(receipt)
            with self.assertRaises(ValueError):
                validate(source, receipt)
        receipt = archive("h4-gate1")
        post = receipt["ledger"]["steps"][0]["post_bits"]
        post.append(["0"*16]*2)
        with self.assertRaises(ValueError):
            h4_math(source, receipt["ledger"])
        post.pop()
        post[7][0] = "8000000000000000"
        with self.assertRaises(ValueError):
            h4_math(source, receipt["ledger"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            strict_json('{"receipt":{"verify":1,"verify":2}}')

    def test_envelope_and_external_pin(self):
        source = SOURCE.read_text()
        for family in ("h3", "h4-gate1"):
            original = archive(family)
            sealed = seal(source, original)
            for mutate in (
                    lambda r: r["verify"].update(decision="FAIL"),
                    lambda r: r["generate"].pop("resident_metric"),
                    lambda r: r.update(ledger_bytes=1),
                    lambda r: r.update(worker_memory_bytes=True),
                    lambda r: r["verify"].update(seconds=float("inf")),
                    lambda r: r["generate"]["supervisor"].update(active_after_cleanup=1),
                    lambda r: r["ledger"]["steps"].reverse()):
                forged = copy.deepcopy(sealed)
                mutate(forged["receipt"])
                with self.assertRaises(ValueError):
                    forged["content_sha256"] = digest(forged["receipt"])
                    verify(source, forged)
            forged = copy.deepcopy(sealed)
            forged["receipt"]["machine"] = "another-machine"
            with self.assertRaisesRegex(ValueError, "content digest mismatch"):
                verify(source, forged)
            forged["content_sha256"] = digest(forged["receipt"])
            self.assertEqual(verify(source, forged)["execution_provenance"], "UNAUTHENTICATED")
            with self.assertRaisesRegex(ValueError, "trusted content"):
                verify(source, forged, expected_digest=sealed["content_sha256"])

    def test_legitimate_fail_and_cli(self):
        data = json.loads(SOURCE.read_text())
        data["budget"] = "0"
        source = json.dumps(data)
        receipt = archive("h3")
        receipt["ledger"] = generate(source)
        for phase in ("generate", "verify"):
            receipt[phase]["decision"] = "FAIL"
        resize(receipt)
        wrapper = seal(source, receipt)
        self.assertEqual(verify(source, wrapper)["decision"], "FAIL")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            src, out = path/"source.json", path/"receipt.json"
            src.write_text(source, encoding="utf-8")
            out.write_text(json.dumps(wrapper), encoding="utf-8")
            flags = ["-"+"O"*sys.flags.optimize] if sys.flags.optimize else []
            run = subprocess.run([sys.executable, "-B", *flags, "-m",
                                  "tools.high_support.strict_hadamard_receipt",
                                  "verify", str(src), str(out)], cwd=ROOT, capture_output=True,
                                 text=True, timeout=25, check=True)
            self.assertEqual(json.loads(run.stdout)["decision"], "FAIL")
