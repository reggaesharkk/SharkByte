# Public distribution content audit

This source tree is assembled from an explicit allowlist: installable package sources, tests, examples, and scoped documentation/evidence. The frozen source archive and wheel are excluded because the immutable archive includes a workstation profile path and an email-shaped value in nested historical evidence. Raw host acceptance logs, Gate 1/2 security audits, saved-run data, WSL paths, personal profile information, and unrelated files are excluded. Qiskit content is a sanitized subset of source/QASM fixtures and probability vectors; raw host reports and the original nested archive are not included.

`PUBLIC_CONTENT_AUDIT.json` records a recursive pattern scan of every staged file and any nested archives for email-shaped values, Windows user-profile paths, Linux home paths, GitHub/AWS credentials, private-key markers, and non-loopback IPv4 literals. Pattern scanning is a screening step, not a complete secret, privacy, or legal review.

The current curated source tree is licensed under Apache License 2.0 for first-party project material. The distribution includes `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`; earlier published MIT revisions remain separately available with their original terms. The excluded frozen archive and wheel were not changed or relicensed.
