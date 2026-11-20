# GCE and Colab moving-branch evidence package

This directory preserves the three supplied files byte-for-byte: the GCE evidence ZIP, the Markdown audit, and its JSON summary. It also preserves the original Colab moving-branch ZIP found in Downloads and checked against the audit's recorded digest. The standard-library verifier is [`tools/high_support/verify_gce_cross_platform_audit.py`](../../tools/high_support/verify_gce_cross_platform_audit.py).

## SHA-256 record

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `sharkbyte-gce-32g-evidence.zip` | 4,399 | `7c6af2e6fa933cc82248d8a778793642ff21b49f8e99467ae882e909e9bd033b` |
| `sharkbyte-moving-cloud-evidence.zip` (Colab) | 3,339 | `30b11f6a4909c83659f8b3d2f2e4fa7ed16dc3634fd58749c946a98da01ab489` |
| `sharkbyte_gce_cross_platform_audit.md` | 2,701 | `9fe11a7c7aa0d5724b383d3a56620ad4df1d454482085bb5d4b0e217ab72c9e2` |
| `sharkbyte_gce_cross_platform_audit.json` | 3,693 | `af8bf924b75ca0a480c99551ddeff7ef7d6bb780284920601aba89391eb2df7c` |

| ZIP member | Bytes | SHA-256 |
|---|---:|---|
| `manifest.json` | 2,709 | `d8102775a6679a945df8aa0ad32e35cacf49015c04c41c09b31a56690d1ba23f` |
| `worker-stderr.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `gce-moving-cloud.json` | 7,903 | `c7647057c449d732c089d9782c9ac1319e2ee5c3d96eb896ce9f4d31733a2f02` |

| Colab ZIP member | Bytes | SHA-256 |
|---|---:|---|
| `manifest.json` | 967 | `ce0c3bf15dd58035ae772d75f21e2dc5b6756d62e4200bef5c3315811b25bfbf` |
| `moving-cloud.json` | 7,887 | `a7060f8151dfc1c09bc7281214abeddae85aae896b464c9734ae3d68b82008c2` |

Run it from the repository root:

```sh
python -B tools/high_support/verify_gce_cross_platform_audit.py
python -B -m unittest tests.test_gce_cross_platform_audit -v
```

The verifier checks both outer archive digests and CRCs, exact ZIP members and safe paths, both receipt digests and sizes, all 13 source hashes against Git commit `7793d5eace34456ce1cc57f85f4d75cf84c8e889`, seeded gate identities, moving-coordinate propagation, mapping counts, and four rational L2 inequalities. It compares seven evidence payload fields and all 13 source hashes across GCE, Colab, Windows ARM64, and Ubuntu WSL2 ARM64.

## Decisions

| Criterion | Decision | What was checked |
|---|---|---|
| Uploaded file identity and ZIP integrity | **PASS** | ZIP SHA-256 `7c6af2e6…bd033b`; all three members pass CRC; archived receipt SHA-256 `c7647057…3a2f02`. Both sidecar hashes are pinned in the verifier. |
| Pinned source provenance | **PASS** | All 13 manifest source hashes match the corresponding Git blobs at `7793d5e…`. |
| Moving-branch replay records | **PASS** | The four 250-gate sequences regenerate from the recorded width/seed pairs; their gate digests and `x`/`cx` coordinate maps match. The 444 single-gate origin count and affine-map counts through four qubits are checked from their exact formulas. |
| Exact rational deletion inequalities | **PASS** | For each seeded case, the exact deleted mass is the square of binary64 `1e-5`; the minimum charge is **42,949,673** of `2^32` ticks, producing the recorded bound `42949673/4294967296000`. The exact squared error is no greater than the squared bound, which is below the requested `1e-3` budget. |
| GCE record compared with Colab, Windows ARM64, and WSL2 | **PASS** | Seven payload fields and the 13 source hashes match across all four receipts. The verifier checks the listed source blobs at both commit IDs: GCE and Colab pin `7793d5e…`; Windows and WSL2 v2 name `6316a85…`. Equal listed files do not imply whole-commit identity. |
| Colab receipt and ZIP | **PASS** | The recovered original ZIP and receipt match the audit's hashes; the Colab manifest, source revision, 13 source hashes, and decisions also pass independent checks. No fresh Colab execution was performed. |
| GCE execution and resource interpretation | **RECORDED ONLY** | This verifier does not rerun the VM workload. The archived host reported 33,658,982,400 bytes of RAM (31.347 GiB), while the sampled worker peak was 58,368,000 bytes (55.664 MiB) and elapsed time was 13.961806 seconds. The worker had a 24 GiB `RLIMIT_AS` virtual-address-space ceiling. Host capacity was available, not consumed; sampled VmRSS is not a strict peak, and `RLIMIT_AS` is not an RSS cap. |
| General performance or memory guarantee | **OPEN** | One workload and one sampled measurement do not establish a general speedup or a hard resident-memory ceiling. |

The GCE and Colab receipts and local platform records concern the restricted signed-permutation set `x`, `z`, and `cx`. Mixing gates are reported as `UNSUPPORTED`. These archives are source-bound records with independently checked arithmetic; they do not authenticate the machine operators or establish a new run on either cloud environment.
