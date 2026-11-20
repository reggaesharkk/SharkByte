# SharkByte — Google Cloud cross-platform evidence audit

**Decision: PASS (recorded evidence verification)** — GCE, Colab, Windows ARM64, and WSL2 ARM64 are consistent for the pinned moving-branch audit.

- Source commit: `7793d5eace34456ce1cc57f85f4d75cf84c8e889`
- GCE ZIP SHA-256: `7c6af2e6fa933cc82248d8a778793642ff21b49f8e99467ae882e909e9bd033b`
- GCE receipt SHA-256: `c7647057c449d732c089d9782c9ac1319e2ee5c3d96eb896ce9f4d31733a2f02`
- GCE archive CRC: **PASS**; receipt digest and length: **MATCH**; 13 source-hash records match.
- Environment: `Linux-6.12.117+deb13-cloud-amd64-x86_64-with-glibc2.41`, Python `3.13.5`.
- Recorded wall time: **13.962 s**; worker exit **0**; timeout **false**.
- Reported host memory: **31.35 GiB**; observed sampled worker peak VmRSS **55.66 MiB**; worker `RLIMIT_AS` **24 GiB**.

## Cross-platform exact-match checks

| Field | Colab | Windows ARM64 | Ubuntu WSL2 ARM64 |
|---|---|---|---|
| `source_hashes` | MATCH | MATCH | MATCH |
| `archived_counterexample` | MATCH | MATCH | MATCH |
| `exhaustive_mappings` | MATCH | MATCH | MATCH |
| `exhaustive_composed_affine_mappings` | MATCH | MATCH | MATCH |
| `randomized_signed_permutation_circuits` | MATCH | MATCH | MATCH |
| `adversarial_replay` | MATCH | MATCH | MATCH |
| `decisions` | MATCH | MATCH | MATCH |

## Independent exact rational inequalities

| Width | Gates | Deletions | Exact squared error | Certified L2 bound | Result |
|---:|---:|---:|---|---|---|
| 5 | 250 | 1 | `34844914372704104359490377921249/348449143727040986586495598010130648530944` | `42949673/4294967296000` | PASS |
| 8 | 250 | 1 | `34844914372704104359490377921249/348449143727040986586495598010130648530944` | `42949673/4294967296000` | PASS |
| 12 | 250 | 1 | `34844914372704104359490377921249/348449143727040986586495598010130648530944` | `42949673/4294967296000` | PASS |
| 20 | 250 | 1 | `34844914372704104359490377921249/348449143727040986586495598010130648530944` | `42949673/4294967296000` | PASS |

## Limitations

- This audit rechecks the archived evidence and the four recorded exact inequalities. It does not rerun the quantum workload on the GCE host or independently authenticate the operator.
- The 32 GiB VM was not memory-stressed. Observed worker memory was small, and `RLIMIT_AS` limits address space, not RSS or total job memory.
- The certified guarantee is restricted to the signed-permutation `x`, `z`, `cx` subset; mixing gates remain unsupported for moving-branch protection.
- A single Colab/GCE timing pair cannot establish performance superiority or reproducible throughput.
- The evidence is ready for an optional new provenance commit; this audit does not modify the SharkByte repository.
