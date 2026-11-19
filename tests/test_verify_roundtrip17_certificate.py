"""Black-box and adversarial tests for independent roundtrip-17 verifier."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_roundtrip17_certificate import (
    VerificationError, _record_sha256, _parse_source, _pairs_from_source, verify,
)


def make_source(lines: list[str]) -> bytes:
    return ("quantum test {\n  qubits 2;\n  shots 1;\n  seed 2;\n" + "".join(
        f"  {line};\n" for line in lines
    ) + "  measure_all;\n}\n").encode()


def make_cert(raw: bytes, *, fake_optimized: bool = False) -> dict:
    import hashlib
    n, gates = _parse_source(raw)
    pairs, rest = _pairs_from_source(gates)
    return reseal({
        "source": "test.sbq", "source_sha256": hashlib.sha256(raw).hexdigest(),
        "qubits": n, "gates": len(gates), "support_cap": 4096,
        "timeout_seconds": 5.0,
        "cancellation_pairs_zero_based": pairs,
        "executed_gates": 0 if fake_optimized else rest,
        "result": "PASS", "reference_checked": False,
        "final_populated_states": 1,
        "probabilities": {"0" * n: 1.0},
    })


def reseal(rec: dict) -> dict:
    rec = deepcopy(rec)
    rec.pop("record_sha256", None)
    rec["record_sha256"] = _record_sha256(rec)
    return rec


class CertificateVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "test.sbq"
        self.certificate = Path(self.temp.name) / "certificate.json"
        self.set_program(["h 0", "rx .25 1", "cp 1.25 0 1", "cp -1.25 0 1", "rx -.25 1", "h 0"])

    def set_program(self, gates):
        raw = make_source(gates)
        self.source.write_bytes(raw)
        self.save_cert(make_cert(raw))

    def save_cert(self, rec):
        self.certificate.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    def test_valid_full_reduction(self):
        out = verify(self.source, self.certificate)
        self.assertEqual(out["status"], "CERTIFICATE_VERIFIED")
        self.assertEqual((out["original_gates"], out["verified_inverse_pairs"], out["remaining_gates"]), (6, 3, 0))

    def test_changed_source_bytes_without_resealing(self):
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        with self.assertRaisesRegex(VerificationError, "source SHA-256 mismatch"):
            verify(self.source, self.certificate)

    def test_forged_pair_with_resealed_digest(self):
        rec = json.loads(self.certificate.read_text())
        rec["cancellation_pairs_zero_based"][0] = [0, 5]
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "indexed cancellation pairs"):
            verify(self.source, self.certificate)

    def test_false_result_with_resealed_digest(self):
        rec = json.loads(self.certificate.read_text())
        rec["probabilities"] = {"00": 0.99999999999}
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "probability"):
            verify(self.source, self.certificate)

    def test_tampered_certificate_digest(self):
        rec = json.loads(self.certificate.read_text())
        rec["executed_gates"] = 2
        self.save_cert(rec)
        with self.assertRaisesRegex(VerificationError, "record SHA-256 mismatch"):
            verify(self.source, self.certificate)

    def test_noninverse_resealed_source_is_not_identity(self):
        self.set_program(["rx .25 1", "rx -.2500000000000001 1"])
        rec = json.loads(self.certificate.read_text())
        rec["executed_gates"] = 0
        rec["cancellation_pairs_zero_based"] = [[0, 1]]
        self.save_cert(reseal(rec))
        with self.assertRaises(VerificationError):
            verify(self.source, self.certificate)

    def test_genuine_small_angle_not_pruned(self):
        self.set_program(["ry .00000000000001 0"])
        rec = json.loads(self.certificate.read_text())
        rec["executed_gates"] = 0
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "executed_gates"):
            verify(self.source, self.certificate)

    def test_swapped_cnot_operands(self):
        self.set_program(["cx 0 1", "cx 1 0"])
        rec = json.loads(self.certificate.read_text())
        rec["cancellation_pairs_zero_based"] = [[0, 1]]
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "indexed cancellation pairs"):
            verify(self.source, self.certificate)

    def test_nonlinear_false_identity(self):
        self.set_program(["h 0", "z 0", "h 0"])
        rec = json.loads(self.certificate.read_text())
        rec["executed_gates"] = 0
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "executed_gates"):
            verify(self.source, self.certificate)

    def test_duplicate_keys_rejected(self):
        self.certificate.write_text('{"source":"a", "source":"b"}', encoding="utf-8")
        with self.assertRaisesRegex(VerificationError, "duplicate certificate key"):
            verify(self.source, self.certificate)

    def test_integer_type_bool_rejected(self):
        rec = json.loads(self.certificate.read_text())
        rec["gates"] = True
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "gates"):
            verify(self.source, self.certificate)

    def test_unsupported_gate_rejected_even_if_hashed(self):
        self.source.write_bytes(make_source(["h 0", "ccx 0 1 0", "h 0"]))
        rec = make_cert(make_source(["h 0", "h 0"]))
        import hashlib
        rec["source_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "unsupported"):
            verify(self.source, self.certificate)

    def test_nonfinal_measurement_rejected(self):
        self.source.write_bytes(make_source(["h 0", "measure_all", "h 0"]))
        import hashlib
        rec = json.loads(self.certificate.read_text())
        rec["source_sha256"] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.save_cert(reseal(rec))
        with self.assertRaisesRegex(VerificationError, "gate outside"):
            verify(self.source, self.certificate)

    def test_original_certificate_digest_matches(self):
        original = Path(__file__).resolve().parents[1] / "evidence/roundtrip17-inverses.json"
        if original.is_file():
            record = json.loads(original.read_text())
            self.assertEqual(_record_sha256({k:v for k,v in record.items() if k!='record_sha256'}), record['record_sha256'])
            self.assertEqual(record['record_sha256'], '6094e0335b402f315d2bef99663a689d5170dc8fccc2ed2d885bb2b4f76d019d')

    def test_full_214_gate_source_against_uploaded_certificate(self):
        root = Path(__file__).resolve().parents[1]
        report = verify(root / "examples/high_support/roundtrip_17q.sbq",
                        root / "evidence/roundtrip17-inverses.json")
        self.assertEqual(report["original_gates"], 214)
        self.assertEqual(report["verified_inverse_pairs"], 107)
        self.assertEqual(report["remaining_gates"], 0)


if __name__ == "__main__":
    unittest.main()