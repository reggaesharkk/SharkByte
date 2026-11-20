# Strict Hadamard receipt validation

I reproduced both reported gaps. Legacy H3 replay accepts an explicit all-zero sparse row because it compares mathematical coordinates after dropping zeros. H3 also replays the inner ledger while ignoring the outer platform and phase decisions. PR #28 tests mathematical archival compatibility and deliberately leaves native output zero signs outside that contract. PR #29 independently reconstructs every dense output word, so it rejects added zero rows and forged zero signs. Its legacy CLI still ignores the surrounding receipt metadata.

I preserve the earlier modules and receipts. I apply the new checks through a separate command. For H3 I require unique, increasing sparse indices, canonical finite binary64 word encodings and no all-zero row. H4 uses a dense vector with a fixed row for each basis coordinate, so an all-zero row at its proper index is legal. H4 replay reconstructs the full sequence including zero signs. H3 still records those signs without independently verifying them.

I check the envelope's exact fields, worker cap, canonical ledger byte count, platform and metric consistency, timings, supervisor exit, Windows cleanup and committed memory, and both phase decisions against independent ledger replay. I reject duplicate JSON keys before validation and verify ordering for sequence data. A valid budget failure returns a verified decision of FAIL and a successful validation exit status. Invalid receipts fail validation with a nonzero exit status.

## Reproduce

From the repository root:

    python -B -m tools.high_support.strict_hadamard_receipt archive evidence/h3/circuit.json evidence/h3/windows-arm64.json
    python -B -m tools.high_support.strict_hadamard_receipt seal evidence/h3/circuit.json evidence/h4-gate1/windows-arm64.json > strict.json
    python -B -m tools.high_support.strict_hadamard_receipt verify evidence/h3/circuit.json strict.json
    python -B -m unittest tests.test_strict_hadamard_receipt tests.test_h4_software

I use UTF-8 for both source and receipt files. The archive command validates legacy envelopes in place. The seal command creates a versioned wrapper whose content hash covers the whole parsed receipt, including the metadata and all recorded bits. I can pass an independently obtained hash with --expected-digest. In archive mode it pins raw file bytes. In verify mode it pins the canonical receipt content. A hash provided by the same receipt detects edits without resealing, but anyone can replace plausible metadata and recompute that hash. An external pin verifies correspondence to the pinned content. Neither establishes who executed the circuit, where execution occurred, or whether the telemetry is truthful. The command reports execution provenance as UNAUTHENTICATED in all modes.

My acceptance boundary separates successful mathematical replay, canonical representation, deterministic bit replay where available, and authenticated execution. The public certified-support API is outside this validation path.
