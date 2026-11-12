# Redistribution rights status — 2026-11-12

> **Historical snapshot:** This document records the initial inventory before the owner supplied authorship/rights confirmation and Apache-2.0 authorization. Its original findings are preserved below as a dated record. The later disposition is in [APACHE_RIGHTS_CLEARANCE_20261112.md](APACHE_RIGHTS_CLEARANCE_20261112.md); that addendum supersedes the former BLOCKED status for the curated public tree only.

## Decision

**BLOCKED: Apache-2.0 redistribution rights are not established for the current public source tree.** No license is selected or applied. This document records the inventory and evidence gap; it does not grant rights, relicense any file, or replace upstream notices. Do not treat public GitHub visibility as permission to relicense.

## Inventory basis

Inventory was derived from `git ls-files` at base commit `95f936aa32e10ee8ef726093889067086e4c4421` (55 tracked files: 8 vendored source/pin entries and 47 Qiskit validation evidence entries). Generated, untracked Python cache files were excluded. No scanned file contained an explicit license/copyright marker; absence of a marker is not evidence of ownership or permission. Per-file byte sizes and SHA-256 digests are recorded in the dated local `VENDORED_RIGHTS_INVENTORY.json` evidence.

## Vendored compiler/runtime source and pin metadata

Every entry below is recorded as `NOT ESTABLISHED` for third-party redistribution rights; the repository contains no per-file permission chain or upstream license attribution sufficient to clear Apache-2.0. Confirm the original author, ownership, and any contributor rights; otherwise replace the component with independently authored or properly licensed code.

| Path | Inventory category | Rights / attribution status |
|---|---|---|
| `sharkbyte_alpha/_vendor/dependencies/8093/web_ide/native_evidence.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/frozen_pins_8099b.json` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/gate2_parent.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/sharkbyte_8097.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/sharkbyte_8098.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/sharkbyte_8099a.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/sharkbyte_8099b.py` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |
| `sharkbyte_alpha/_vendor/source_pins.json` | vendored_source_or_pin_metadata | NOT ESTABLISHED; No per-file attribution/rights evidence found by marker scan; obtain ownership, contributor permission, or compatible upstream license before redistribution under Apache-2.0 |

## Qiskit comparison fixtures and evidence

These 47 tracked records are validation inputs/results and provenance material associated with the separately scoped Qiskit replay. The comparison establishes numerical results, not copyright ownership. Their individual paths, byte lengths, SHA-256 digests, and rights statuses are listed below; each has `NOT ESTABLISHED` rights status and no detected license/copyright marker. Obtain rights or remove/replace each item before selecting a license that covers the complete repository.

| Path | Bytes | SHA-256 | Rights status |
|---|---:|---|---|
| `evidence/qiskit_0.2.2a1/INDEPENDENT_EVIDENCE_REVIEW.json` | 6444 | `dcafc32622dfbb387f2c51c305e23f9a6db70fb7d07f6246c0589a21f7b54c95` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/PUBLIC_EVIDENCE_MANIFEST.json` | 7259 | `a4002f1246f8fe7aca202606a701a73a478afdcd68ee1da7d7b398177fe65530` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/bell.qasm` | 125 | `52b456fd583d44c1ed379a0a72de5ce555d9d294bf66cc29ac7a43816ed34285` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/bell.sbq` | 74 | `3b31a2e27bbdc074678bb4370e505a30cf279173dffa4cdbd26132fbcac9de12` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/cp_interference.qasm` | 159 | `9343bc69b875a15f01cd3f90ef194a0e9895376d20f696cf4164b90e1234cb18` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/cp_interference.sbq` | 69 | `1436115405342d8c5dcf3e56ca8995518470d67e4c7fad8863cfeceab486dcca` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/ghz.qasm` | 161 | `46b781d9febe8d138180cca9ab49d2162eaffb3338b07d66e4f1c60e7dd3c33b` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/ghz.sbq` | 53 | `069b44cc14660c9b51639e14d69803b9c761d8aa96a7b9922285a8c318cd676e` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_0.qasm` | 169 | `9fddc568fcdfbdff2d8d9cc81d3572848d5fae9db3bca5a92330f4eafd0099ac` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_0.sbq` | 122 | `8e705d34e9bec06c438e4482841c5b81517b59b82adb37009e21b0f87c84d482` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_1.qasm` | 169 | `27baab447057575390d52446709a8b9820fd3236e3a47053509b9eba32d997ca` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_1.sbq` | 122 | `f6406485e1db544532f0bfdfe29162e2009b6e8a12844ae8c0adbb553a72e72b` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_2.qasm` | 169 | `2ae3c9e940839022c06e4015e930bb5c5f8e171208d5d14afc41a1da61aa1647` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_2.sbq` | 122 | `285595476281ca536a1d25df4e84a1a88bc5d31cad037946135a83ddde2990fe` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_3.qasm` | 170 | `4fb4ced6b98868e16cda9fd2f2974d021832759af2c0253da8422a1e6b80fd23` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/hybrid_3.sbq` | 121 | `d820dfd34a3703e2290ae9cc2171478a26a640380dd718806e803dd22554a2b4` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qft6.qasm` | 929 | `0fbad87bf25555b8082e6df0c10a0e17edb0b9c7c5e1a0312744d5b888e82044` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qft6.sbq` | 612 | `f6ef0ea5469147fe3b244cd7d75d11cd49d7243ab23d88ce5c073ac54a16de0c` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qft6_inverse.qasm` | 1663 | `546013667f8dc6cc54c2237f54d0268f061de398db15b2e2e375b8f7eb00bfbf` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qft6_inverse.sbq` | 1153 | `6c89c9ad6e3d44f289c257120238a32adc099fc050cd34454360c89af547194e` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qpe5_constructed.qasm` | 908 | `b9651de88498b3553d6f749c6e33b9caa99d7b47c10c1d8542619b4fbeb4a59f` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/qpe5_constructed.sbq` | 542 | `c543c87f74e2069afbac23db8b651d7f23a58f01b6dc2a7a3eeef584b898646f` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_00.qasm` | 295 | `982aecfb024a7f79976d28e680bc2406a79ab4768edf37b2a85a65ddbf27e1c1` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_00.sbq` | 127 | `a83f1ef5d19f0e33a834b7201f110db6584adefc030e1d493ba2ff2c28c48762` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_01.qasm` | 316 | `c87e51dd431b42325810aded1fc171e39a4c03fbbaddc1ac197a8e7979a86f97` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_01.sbq` | 127 | `f6facfd3d32e70033c5c5d71292b813c209cc5dc43e391c3ca152f01934388cc` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_02.qasm` | 282 | `cc10e4cca32dc1009608e6b63c82882e91760bada0c7bbb22dd944a72bcc8fdc` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_02.sbq` | 113 | `b82b55354cc4d072fddfc9cf2f43ade850fe435829917d01e850adcc1b8c052e` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_03.qasm` | 325 | `b21094f6bd6821c3bc48397ccd4e3651fe35b892dba537ffa5677f78e2cbc997` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_03.sbq` | 136 | `22e99a44618f5546916d914d24e7a20ea036cc4af65013c90b538dca02cef82e` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_04.qasm` | 260 | `f9e192f61f03badb95628157c265958120c69f5e68007a7ac6bf2d95fa590261` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_04.sbq` | 113 | `652511174f489cec5a549f1d43be6cd7bc5f339984e08b8adcf040b15522a49f` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_05.qasm` | 310 | `c582395bb15fa11927560e30ebdca2c54f0567d709180753b08b91f79816deed` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_05.sbq` | 121 | `355805a17708aa585e5a8597954ecf6abe8e593d42f73062895108f327ce3bc9` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_06.qasm` | 346 | `4d80f3f51a3003c6c25ed1da0c2ac99d10dc17455e19a7e19db67e9141b6660b` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_06.sbq` | 140 | `9ac4ff09c87f3ed71b64fb86aed496f6ee3d95ef9e4f2499b7e0233c2e3709f5` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_07.qasm` | 254 | `77994b0cb225acfa065dfac36ac6583b8e913554ca973f770beb07cc365fb525` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_07.sbq` | 115 | `c254ab83ab3534329d04d40a2f9b04ad4b7ae5e59832e30391882596ab774dac` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_08.qasm` | 281 | `4ebda368dc3b53007559d16d37612b07927e74b080c0b2e8dd79c97b52ea0524` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_08.sbq` | 113 | `e756cefe39477d2a0b3803631496b76d24e960ac4bd6d88f2e698f80224c0781` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_09.qasm` | 246 | `60381f952a5b56eb94d1d690e6230460a10f64f00543a53e349775f492c3e45f` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/random_09.sbq` | 116 | `39697e6b7885bb64c1ba8b5862d22bebac8a2dd5d3028957c90213c0e68417c9` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/x0_bit_order.qasm` | 110 | `56f07c4b06ed9d18dd8964d4b54fe5b3fd98a0c2189cd2e2010d7f7b1308af11` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/x0_bit_order.sbq` | 34 | `4224fd17e82e81b86a68947a5258a42778abf9c6cd16858d27e3d8c70f31a470` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/x1_bit_order.qasm` | 110 | `779bce3d0da768dbb5ad758413a3b7fc131f1e4324b6ca45f027cdbb4ba1c8fb` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/fixtures/x1_bit_order.sbq` | 34 | `10ea7586314ad6faf700a1162af326661a473ed07dd35019c8bda76ccd3c904b` | NOT ESTABLISHED |
| `evidence/qiskit_0.2.2a1/qiskit_probability_comparison.json` | 23186 | `8aa76234624529a94543bf32ff0c36983a01a6804508db7acb1be4464b766b95` | NOT ESTABLISHED |

## Required clearance actions

1. Establish authorship or obtain written permission for every vendored source/pin file and every redistributed fixture/evidence file, or remove/replace files lacking permission.
2. Record upstream project/version/source URL and the exact applicable license for each retained third-party component.
3. Preserve all required copyright, attribution, NOTICE, and license text; check Apache-2.0 compatibility component by component.
4. Obtain the repository owner’s explicit license selection/authorization before adding a top-level license.
5. Re-run the public file audit and package checks after rights remediation; update the inventory hashes without rewriting historical evidence.

Until these actions are complete, there is no defensible Apache-2.0 clearance and no release-ready license grant. The existing native-disabled policy and Gate 1 status are independent and unchanged.
