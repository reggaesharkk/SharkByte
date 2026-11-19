import copy
import io
import json
import pathlib
import unittest
import warnings
import zipfile

from tools.high_support import verify_gce_cross_platform_audit as audit


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GceCrossPlatformAuditTests(unittest.TestCase):
    def test_archived_audit_verifies(self):
        report = audit.verify_bundle(ROOT)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["pinned_source_hashes_checked"], 13)
        self.assertEqual(report["colab_status"].split(";")[0], "PASS")
        self.assertEqual(len(report["exact_seeded_inequalities"]), 4)

    def test_seeded_gate_substitution_is_rejected(self):
        bundle = audit.read_archive(
            (ROOT / audit.EVIDENCE_DIR / audit.ARCHIVE_NAME).read_bytes()
        )
        receipt = json.loads(bundle["gce-moving-cloud.json"])
        rows = copy.deepcopy(receipt["randomized_signed_permutation_circuits"])
        rows[0]["gate_sha256"] = "0" * 64
        with self.assertRaises(audit.VerificationError):
            audit.verify_seeded_rows(rows)

    def test_forged_exact_bound_is_rejected(self):
        bundle = audit.read_archive(
            (ROOT / audit.EVIDENCE_DIR / audit.ARCHIVE_NAME).read_bytes()
        )
        receipt = json.loads(bundle["gce-moving-cloud.json"])
        rows = copy.deepcopy(receipt["randomized_signed_permutation_circuits"])
        rows[2]["certified_l2_bound"] = "1/1000"
        with self.assertRaises(audit.VerificationError):
            audit.verify_seeded_rows(rows)

    def test_pinned_source_hash_substitution_is_rejected(self):
        bundle = audit.read_archive(
            (ROOT / audit.EVIDENCE_DIR / audit.ARCHIVE_NAME).read_bytes()
        )
        manifest = json.loads(bundle["manifest.json"])
        manifest["source_hashes"]["README.md"] = "0" * 64
        with self.assertRaises(audit.VerificationError):
            audit._verify_source_hashes(manifest, manifest, ROOT)

    def test_duplicate_zip_members_are_rejected(self):
        payload = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(payload, "w") as archive:
                for name in sorted(audit.MEMBERS):
                    archive.writestr(name, b"{}")
                archive.writestr("manifest.json", b"{}")
        with self.assertRaises(audit.VerificationError):
            audit.read_archive(payload.getvalue(), check_outer_digest=False)

    def test_traversal_zip_member_is_rejected(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("../manifest.json", b"{}")
            archive.writestr("worker-stderr.log", b"")
            archive.writestr("gce-moving-cloud.json", b"{}")
        with self.assertRaises(audit.VerificationError):
            audit.read_archive(payload.getvalue(), check_outer_digest=False)


if __name__ == "__main__":
    unittest.main()
