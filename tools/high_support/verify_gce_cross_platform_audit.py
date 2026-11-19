#!/usr/bin/env python3
"""Independently verify the archived GCE moving-branch audit bundle.

This verifier uses only the Python standard library and the pinned Git object.
It does not execute the cloud workload and does not treat the supplied audit
summary as proof of a computation that is absent from the archive.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import pathlib
import random
import subprocess
import sys
import zipfile
from fractions import Fraction
from pathlib import PurePosixPath


BASELINE_COMMIT = "7793d5eace34456ce1cc57f85f4d75cf84c8e889"
EVIDENCE_DIR = pathlib.Path("evidence/gce-moving-branch-cross-platform-20261120")
ARCHIVE_NAME = "sharkbyte-gce-32g-evidence.zip"
COLAB_ARCHIVE_NAME = "sharkbyte-moving-cloud-evidence.zip"
AUDIT_JSON_NAME = "sharkbyte_gce_cross_platform_audit.json"
AUDIT_MD_NAME = "sharkbyte_gce_cross_platform_audit.md"
EXPECTED_FILE_HASHES = {
    ARCHIVE_NAME: "7c6af2e6fa933cc82248d8a778793642ff21b49f8e99467ae882e909e9bd033b",
    COLAB_ARCHIVE_NAME: "30b11f6a4909c83659f8b3d2f2e4fa7ed16dc3634fd58749c946a98da01ab489",
    AUDIT_JSON_NAME: "af8bf924b75ca0a480c99551ddeff7ef7d6bb780284920601aba89391eb2df7c",
    AUDIT_MD_NAME: "9fe11a7c7aa0d5724b383d3a56620ad4df1d454482085bb5d4b0e217ab72c9e2",
}
EXPECTED_RECEIPT_SHA256 = "c7647057c449d732c089d9782c9ac1319e2ee5c3d96eb896ce9f4d31733a2f02"
MEMBERS = {"manifest.json", "worker-stderr.log", "gce-moving-cloud.json"}
COLAB_MEMBERS = {"manifest.json", "moving-cloud.json"}
EXPECTED_MEMBER_HASHES = {
    "manifest.json": (2709, "d8102775a6679a945df8aa0ad32e35cacf49015c04c41c09b31a56690d1ba23f"),
    "worker-stderr.log": (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    "gce-moving-cloud.json": (7903, EXPECTED_RECEIPT_SHA256),
}
EXPECTED_COLAB_MEMBER_HASHES = {
    "manifest.json": (967, "ce0c3bf15dd58035ae772d75f21e2dc5b6756d62e4200bef5c3315811b25bfbf"),
    "moving-cloud.json": (7887, "a7060f8151dfc1c09bc7281214abeddae85aae896b464c9734ae3d68b82008c2"),
}
COMPARE_FIELDS = (
    "source_hashes",
    "archived_counterexample",
    "exhaustive_mappings",
    "exhaustive_composed_affine_mappings",
    "randomized_signed_permutation_circuits",
    "adversarial_replay",
    "decisions",
)
SEED_CASES = ((5, 17), (8, 29), (12, 43), (20, 71))
TICKS = 1 << 32


class VerificationError(ValueError):
    """Raised when a supplied artifact contradicts the archived evidence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(data: bytes, label: str):
    try:
        return json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label} is not valid UTF-8 JSON: {exc}") from exc


def _safe_member(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and str(path) == name


def read_archive(data: bytes, *, check_outer_digest: bool = True,
                 expected_members: set[str] = MEMBERS,
                 expected_outer_digest: str | None = None) -> dict[str, bytes]:
    if expected_outer_digest is None:
        expected_outer_digest = EXPECTED_FILE_HASHES[ARCHIVE_NAME]
    if check_outer_digest:
        _require(_sha256(data) == expected_outer_digest,
                 "ZIP SHA-256 differs from the supplied original")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            _require(len(names) == len(set(names)), "ZIP contains duplicate member names")
            _require(set(names) == expected_members, f"unexpected ZIP members: {sorted(names)}")
            for info in infos:
                _require(_safe_member(info.filename), f"unsafe ZIP member path: {info.filename!r}")
                mode = info.external_attr >> 16
                _require(not info.is_dir() and (mode & 0o170000) != 0o120000,
                         f"ZIP member is not a regular file: {info.filename!r}")
            bad = archive.testzip()
            _require(bad is None, f"ZIP CRC/decompression failure at {bad!r}")
            return {name: archive.read(name) for name in names}
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise VerificationError(f"invalid evidence ZIP: {exc}") from exc


def _ceil_sqrt_fraction(value: Fraction) -> int:
    """Return the least integer n with n**2 >= value, using integer math."""
    _require(value >= 0, "square-root input must be nonnegative")
    root = math.isqrt(value.numerator // value.denominator)
    if root * root * value.denominator < value.numerator:
        root += 1
    return root


def _expected_gates(width: int, seed: int) -> list[tuple]:
    rng = random.Random(width * 1000 + seed)
    gates = []
    for _ in range(250):
        op = rng.choice(("x", "z", "cx"))
        if op == "cx":
            gates.append((op, *rng.sample(range(width), 2)))
        else:
            gates.append((op, rng.randrange(width)))
    return gates


def _propagate_coordinate(origin: int, gates: list[tuple]) -> int:
    position = origin
    for gate in gates:
        if gate[0] == "x":
            position ^= 1 << gate[1]
        elif gate[0] == "cx":
            if position & (1 << gate[1]):
                position ^= 1 << gate[2]
        elif gate[0] != "z":
            raise VerificationError(f"unsupported operation in seeded circuit: {gate[0]!r}")
    return position


def verify_seeded_rows(rows: list[dict]) -> list[dict]:
    _require(isinstance(rows, list) and len(rows) == len(SEED_CASES),
             "the receipt must contain exactly four seeded cases")
    checked = []
    budget = Fraction("1e-3")
    # The sole unprotected input coordinate is basis 2, whose real amplitude
    # is the binary64 value 1e-5. The receipt reports one deleted coordinate.
    deleted_mass = Fraction.from_float(1e-5) ** 2
    minimum_ticks = _ceil_sqrt_fraction(deleted_mass / budget**2 * TICKS**2)
    bound = budget * minimum_ticks / TICKS
    _require(minimum_ticks == 42949673, "unexpected minimum exact tick charge")

    for row, (width, seed) in zip(rows, SEED_CASES):
        _require(isinstance(row, dict), f"seed case {width}/{seed} is not an object")
        gates = _expected_gates(width, seed)
        gate_digest = _sha256(json.dumps(gates, separators=(",", ":")).encode("ascii"))
        _require(row.get("width") == width and row.get("seed") == seed,
                 f"seed case identity differs at {width}/{seed}")
        _require(row.get("gates") == len(gates) == 250,
                 f"seed case gate count differs at {width}/{seed}")
        _require(row.get("gate_sha256") == gate_digest,
                 f"seeded gate sequence digest differs at {width}/{seed}")
        origins = [0, 1, (1 << width) - 1]
        positions = [[origin, _propagate_coordinate(origin, gates)] for origin in origins]
        _require(row.get("origins") == origins, f"protected origins differ at {width}/{seed}")
        _require(row.get("final_positions") == positions,
                 f"exact moving-coordinate replay differs at {width}/{seed}")
        _require(row.get("events") == 1 and row.get("deleted_coordinates") == 1,
                 f"deletion-event counts differ at {width}/{seed}")
        _require(row.get("exact_squared_error") == str(deleted_mass),
                 f"exact squared deletion error differs at {width}/{seed}")
        _require(row.get("certified_l2_bound") == str(bound),
                 f"certified rational bound differs at {width}/{seed}")
        _require(deleted_mass <= bound**2 <= budget**2,
                 f"exact L2 inequality fails at {width}/{seed}")
        checked.append({
            "width": width,
            "seed": seed,
            "gate_sha256": gate_digest,
            "exact_squared_error": str(deleted_mass),
            "minimum_ticks": minimum_ticks,
            "certified_l2_bound": str(bound),
            "inequality": "PASS",
        })
    return checked


def _verify_mapping_counts(receipt: dict) -> None:
    maps = receipt.get("exhaustive_mappings", {})
    _require(maps.get("families") == ["x", "z", "cx"],
             "single-gate mapping family list differs")
    _require(maps.get("widths") == [1, 2, 3, 4], "single-gate mapping widths differ")
    _require(maps.get("exhaustive_over_each_legal_single_gate_and_basis_origin") is True,
             "single-gate mapping record does not claim exhaustive origin coverage")
    expected_single = sum((2 * width + width * (width - 1)) * (1 << width)
                          for width in range(1, 5))
    _require(expected_single == 444 and maps.get("individual_gate_origin_mappings") == expected_single,
             "single-gate/origin mapping count differs from exact enumeration size")

    affine = receipt.get("exhaustive_composed_affine_mappings")
    _require(isinstance(affine, list) and len(affine) == 4,
             "expected four affine-closure records")
    for row, width in zip(affine, range(1, 5)):
        dimension = 1 << width
        linear_maps = math.prod(dimension - (1 << i) for i in range(width))
        affine_maps = linear_maps * dimension
        _require(row.get("qubits") == width, f"affine width differs at {width}")
        _require(row.get("affine_coordinate_maps") == affine_maps
                 and row.get("expected_affine_maps") == affine_maps,
                 f"affine map count differs at {width}")
        _require(row.get("basis_images_checked") == affine_maps * dimension,
                 f"affine basis-image count differs at {width}")
        _require(row.get("production_propagation_edges") == affine_maps - 1,
                 f"affine propagation edge count differs at {width}")
        _require(row.get("closure_generators") == ["x", "cx"]
                 and row.get("z_coordinate_action") == "identity; sign is separately Fraction-replayed",
                 f"affine closure semantics differ at {width}")


def _verify_counterexample_and_decisions(receipt: dict) -> None:
    counterexample = receipt.get("archived_counterexample", {})
    fixed = counterexample.get("fixed_mode", {})
    moving = counterexample.get("moving_mode", {})
    _require(fixed.get("status") == "PASS" and fixed.get("final_support") == 1,
             "fixed-index counterexample record differs")
    _require(fixed.get("deleted") == [[0, "0x1.ad7f29abcaf48p-24", "0x0.0p+0"]],
             "fixed-index counterexample deletion witness differs")
    _require(moving.get("status") == "PASS" and moving.get("verifier_status") == "PASS"
             and moving.get("final_support") == 2
             and moving.get("final_positions") == [[1, 0]]
             and moving.get("exact_squared_error") == "0/1",
             "moving-index counterexample replay differs")

    adversarial = receipt.get("adversarial_replay", {})
    expected_forgery_rejections = {
        "wrong-final-map", "wrong-origin", "wrong-policy",
        "deleting-current-protected-coordinate",
    }
    _require(set(adversarial.get("forged_certificates_rejected", ())) == expected_forgery_rejections,
             "adversarial forged-certificate decisions differ")
    _require(adversarial.get("mixing_gate_status") == "UNSUPPORTED"
             and "outside the certified signed-permutation subset" in adversarial.get("mixing_gate_reason", ""),
             "mixing-gate refusal record differs")

    decisions = receipt.get("decisions", {})
    expected_decisions = {
        "archived_counterexample_repaired_in_moving_mode": "PASS",
        "fixed_index_mode_preserved": "PASS",
        "full_affine_coordinate_mapping_closure_through_four_qubits": "PASS",
        "mixing_gates_rejected": "PASS",
        "moving_protection_through_mixing_gates": "UNSUPPORTED",
        "performance_generalization": "OPEN",
        "randomized_larger_circuits_exactly_replayed": "PASS",
        "single_gate_mappings_all_origins_through_four_qubits": "PASS",
    }
    _require(decisions == expected_decisions, "moving-branch decision table differs")


def _verify_cross_platform(receipt: dict, colab_receipt: dict,
                           root: pathlib.Path, audit: dict) -> tuple[dict[str, str], dict[str, int]]:
    paths = {
        "Google Colab": None,
        "Windows ARM64": root / "evidence/moving-branch-protection-windows-arm64-v2.json",
        "Ubuntu WSL2 ARM64": root / "evidence/moving-branch-protection-ubuntu-wsl2-arm64-v2.json",
    }
    commits = {}
    source_counts = {}
    for label, path in paths.items():
        if label == "Google Colab":
            platform_record = colab_receipt
        else:
            platform_record = _json_bytes(path.read_bytes(), str(path))
        commits[label] = platform_record.get("implementation_commit")
        _require(platform_record.get("source_hashes") == receipt.get("source_hashes"),
                 f"{label} source-hash set differs from GCE")
        source_counts[label] = _verify_source_hashes(
            {"source_hashes": platform_record.get("source_hashes")},
            platform_record, root, commit=platform_record.get("implementation_commit"),
        )
        for field in COMPARE_FIELDS:
            _require(platform_record.get(field) == receipt.get(field),
                     f"{label} field differs from GCE: {field}")
            _require(audit.get("comparison_equalities", {}).get(label, {}).get(field) is True,
                     f"audit sidecar does not record {label}/{field} equality")
    _require(commits.get("Google Colab") == BASELINE_COMMIT
             and commits.get("Windows ARM64") == "6316a85f2870ba6ec37e51551420acd2837f78f5"
             and commits.get("Ubuntu WSL2 ARM64") == "6316a85f2870ba6ec37e51551420acd2837f78f5",
             "the platform evidence commit IDs differ from the audited records")
    # Colab and GCE use the same commit. The Windows and WSL2 receipts use a
    # different commit, but their 13 source hashes match the pinned GCE tree.
    # This proves listed-file identity without implying whole-commit identity.

    return commits, source_counts


def _verify_source_hashes(manifest: dict, receipt: dict, root: pathlib.Path,
                          *, commit: str = BASELINE_COMMIT) -> int:
    expected = manifest.get("source_hashes")
    _require(isinstance(expected, dict) and len(expected) == 13,
             "manifest must contain the 13 pinned source hashes")
    _require(receipt.get("source_hashes") == expected,
             "GCE receipt source hashes differ from the manifest")
    for relative, digest in expected.items():
        _require(_safe_member(relative),
                 f"unsafe source path in manifest: {relative!r}")
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit}:{relative}"],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise VerificationError(f"cannot read {commit} source {relative}: {exc}") from exc
        _require(_sha256(result.stdout) == digest,
                 f"{commit} source hash mismatch: {relative}")
    return len(expected)


def verify_bundle(root: pathlib.Path) -> dict:
    root = root.resolve()
    evidence = root / EVIDENCE_DIR
    originals = {}
    for name, expected_hash in EXPECTED_FILE_HASHES.items():
        path = evidence / name
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise VerificationError(f"cannot read evidence file {path}: {exc}") from exc
        _require(_sha256(data) == expected_hash, f"original artifact hash mismatch: {name}")
        originals[name] = data

    members = read_archive(originals[ARCHIVE_NAME])
    for name, (expected_size, expected_digest) in EXPECTED_MEMBER_HASHES.items():
        content = members[name]
        _require(len(content) == expected_size and _sha256(content) == expected_digest,
                 f"archived member size/digest differs: {name}")
    manifest = _json_bytes(members["manifest.json"], "GCE manifest")
    receipt_bytes = members["gce-moving-cloud.json"]
    receipt = _json_bytes(receipt_bytes, "GCE receipt")
    audit = _json_bytes(originals[AUDIT_JSON_NAME], "cross-platform audit JSON")
    colab_members = read_archive(
        originals[COLAB_ARCHIVE_NAME], expected_members=COLAB_MEMBERS,
        expected_outer_digest=EXPECTED_FILE_HASHES[COLAB_ARCHIVE_NAME],
    )
    colab_manifest = _json_bytes(colab_members["manifest.json"], "Colab manifest")
    colab_receipt_bytes = colab_members["moving-cloud.json"]
    colab_receipt = _json_bytes(colab_receipt_bytes, "Colab receipt")
    colab_member_hashes = EXPECTED_COLAB_MEMBER_HASHES
    for name, (expected_size, expected_digest) in colab_member_hashes.items():
        content = colab_members[name]
        _require(len(content) == expected_size and _sha256(content) == expected_digest,
                 f"Colab archive member size/digest differs: {name}")

    _require(manifest.get("schema") == "sharkbyte/gce-existing-vm-v1"
             and manifest.get("status") == "PASS", "GCE manifest schema/status differs")
    _require(manifest.get("source_revision") == BASELINE_COMMIT,
             "GCE manifest is not pinned to the expected source revision")
    _require(receipt.get("schema") == "sharkbyte/moving-branch-protection-evidence-v1"
             and receipt.get("implementation_commit") == BASELINE_COMMIT,
             "GCE receipt schema or implementation revision differs")
    _require(manifest.get("receipt_file") == "gce-moving-cloud.json"
             and manifest.get("receipt_bytes") == len(receipt_bytes)
             and manifest.get("receipt_sha256") == _sha256(receipt_bytes)
             and manifest.get("receipt_sha256") == EXPECTED_RECEIPT_SHA256,
             "manifest receipt length/digest does not match archived receipt")
    _require(not members["worker-stderr.log"], "successful archived worker stderr is not empty")
    checks = manifest.get("checks")
    _require(isinstance(checks, dict) and checks and all(value is True for value in checks.values()),
             "GCE manifest contains a failed or missing recorded check")
    source_count = _verify_source_hashes(manifest, receipt, root)

    _require(colab_manifest.get("schema") == "sharkbyte/colab-moving-cloud-manifest-v1"
             and colab_manifest.get("status") == "PASS"
             and colab_manifest.get("source_commit") == BASELINE_COMMIT,
             "Colab manifest schema/status/source revision differs")
    _require(colab_receipt.get("schema") == "sharkbyte/moving-branch-protection-evidence-v1"
             and colab_receipt.get("implementation_commit") == BASELINE_COMMIT,
             "Colab receipt schema or implementation revision differs")
    _require(colab_manifest.get("receipt_bytes") == len(colab_receipt_bytes)
             and colab_manifest.get("receipt_sha256") == _sha256(colab_receipt_bytes)
             and colab_manifest.get("receipt_sha256") == EXPECTED_COLAB_MEMBER_HASHES["moving-cloud.json"][1]
             and colab_manifest.get("worker_exit") == 0,
             "Colab manifest receipt length/digest/exit does not match archived receipt")
    _require(colab_manifest.get("checks") == colab_receipt.get("decisions"),
             "Colab manifest decisions differ from its receipt")
    colab_source_count = _verify_source_hashes(
        {"source_hashes": colab_receipt.get("source_hashes")}, colab_receipt, root,
    )
    _require(colab_receipt.get("source_hashes") == receipt.get("source_hashes"),
             "Colab and GCE source hash sets differ")

    _require(audit.get("schema") == "sharkbyte/gce-colab-arm64-cross-platform-audit-v1"
             and audit.get("result") == "PASS", "audit sidecar schema/result differs")
    _require(audit.get("scope") == "source-bound recorded moving-branch certificate comparison only; no new execution of VM source",
             "audit sidecar scope differs")
    _require(audit.get("gce", {}).get("receipt_sha256") == _sha256(receipt_bytes),
             "audit sidecar receipt digest differs")
    _require(audit.get("gce", {}).get("source_revision") == BASELINE_COMMIT,
             "audit sidecar source revision differs")
    colab_audit = audit.get("colab", {})
    _require(colab_audit.get("source_revision") == BASELINE_COMMIT
             and colab_audit.get("zip_sha256") == EXPECTED_FILE_HASHES[COLAB_ARCHIVE_NAME]
             and colab_audit.get("receipt_sha256") == _sha256(colab_receipt_bytes)
             and colab_audit.get("elapsed_seconds") == colab_manifest.get("elapsed_seconds"),
             "audit sidecar Colab metadata differs from archived receipt")

    _verify_mapping_counts(receipt)
    _verify_counterexample_and_decisions(receipt)
    cases = verify_seeded_rows(receipt.get("randomized_signed_permutation_circuits"))
    audit_cases = audit.get("exact_bound_checks")
    _require(isinstance(audit_cases, list) and len(audit_cases) == len(cases),
             "audit sidecar exact-bound case count differs")
    for archived, computed in zip(audit_cases, cases):
        for key in ("width", "seed", "exact_squared_error", "certified_l2_bound"):
            _require(archived.get(key) == computed[key],
                     f"audit sidecar bound field differs: {key} at {computed['width']}/{computed['seed']}")
        _require(archived.get("inequality_holds") is True,
                 f"audit sidecar does not record inequality pass at {computed['width']}/{computed['seed']}")

    platform_commits, platform_source_counts = _verify_cross_platform(
        receipt, colab_receipt, root, audit,
    )

    memtotal = manifest.get("memtotal_bytes")
    sampled_rss = manifest.get("observed_worker_peak_rss_bytes")
    address_limit = manifest.get("worker_rlimit_as_bytes")
    elapsed = manifest.get("wall_elapsed_seconds")
    _require(manifest.get("worker_exit_code") == 0 and manifest.get("timed_out") is False,
             "GCE worker exit/timeout result differs")
    _require(isinstance(elapsed, (int, float)) and elapsed <= manifest.get("wall_deadline_seconds", 0),
             "GCE wall deadline is invalid or exceeded")
    _require(memtotal == audit.get("gce", {}).get("ram_reported_bytes")
             and sampled_rss == audit.get("gce", {}).get("worker_peak_rss_sampled_bytes")
             and address_limit == audit.get("gce", {}).get("worker_rlimit_as_bytes")
             and elapsed == audit.get("gce", {}).get("elapsed_seconds")
             and manifest.get("receipt_bytes") == audit.get("gce", {}).get("receipt_size_bytes")
             and manifest.get("receipt_sha256") == audit.get("gce", {}).get("receipt_sha256")
             and manifest.get("worker_exit_code") == audit.get("gce", {}).get("worker_exit_code")
             and manifest.get("timed_out") == audit.get("gce", {}).get("worker_timed_out"),
             "GCE resource measurements differ from audit sidecar")
    _require(manifest.get("worker_rlimit_as_is_rss_limit") is False,
             "RLIMIT_AS must not be described as a resident-memory limit")

    return {
        "status": "PASS",
        "archive_sha256": EXPECTED_FILE_HASHES[ARCHIVE_NAME],
        "receipt_sha256": _sha256(receipt_bytes),
        "manifest_members": sorted(members),
        "pinned_source_revision": BASELINE_COMMIT,
        "pinned_source_hashes_checked": source_count,
        "colab_source_hashes_checked": colab_source_count,
        "platform_source_hashes_checked": platform_source_counts,
        "single_gate_origin_mappings": receipt["exhaustive_mappings"]["individual_gate_origin_mappings"],
        "affine_maps_by_width": [row["affine_coordinate_maps"]
                                  for row in receipt["exhaustive_composed_affine_mappings"]],
        "basis_images_checked_width_4": receipt["exhaustive_composed_affine_mappings"][-1]["basis_images_checked"],
        "exact_seeded_inequalities": cases,
        "matched_platform_records": ["Google Colab x86_64", "Windows ARM64", "Ubuntu WSL2 ARM64"],
        "platform_commit_ids": {
            "gce": receipt["implementation_commit"],
            "google_colab": platform_commits["Google Colab"],
            "windows_arm64": platform_commits["Windows ARM64"],
            "ubuntu_wsl2_arm64": platform_commits["Ubuntu WSL2 ARM64"],
        },
        "platform_commit_note": "Colab and GCE share a commit; Windows and WSL2 use another commit whose 13 listed source hashes match",
        "colab_status": "PASS; original archive and receipt hashes, manifest, source blobs, and seven payload fields verified",
        "colab_archive_sha256": EXPECTED_FILE_HASHES[COLAB_ARCHIVE_NAME],
        "colab_receipt_sha256": _sha256(colab_receipt_bytes),
        "colab_wall_elapsed_seconds": colab_manifest["elapsed_seconds"],
        "gce_host_ram_bytes": memtotal,
        "gce_host_ram_gib": round(memtotal / (1024 ** 3), 3),
        "worker_peak_rss_sampled_bytes": sampled_rss,
        "worker_peak_rss_sampled_mib": round(sampled_rss / (1024 ** 2), 3),
        "worker_rlimit_as_bytes": address_limit,
        "worker_rlimit_as_gib": address_limit / (1024 ** 3),
        "worker_wall_elapsed_seconds": elapsed,
        "worker_exit_code": manifest["worker_exit_code"],
        "worker_timed_out": manifest["timed_out"],
        "resource_limit_note": "host capacity was available, not consumed; sampled VmRSS is not a strict peak; RLIMIT_AS is virtual address space, not an RSS cap",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[2],
                        help="repository root (default: inferred from this script)")
    args = parser.parse_args(argv)
    try:
        report = verify_bundle(args.repo)
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
