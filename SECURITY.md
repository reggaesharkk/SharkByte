# Security and resource boundaries

This experimental toolchain is not a security sandbox. VM step, qubit, shot, source-size, and iteration limits do not replace OS process isolation, CPU/memory quotas, or wall-clock enforcement. Do not run untrusted programs in a sensitive environment.

The native interpreter and Direct AArch64 backends are intentionally refused with `native backends are disabled: containment unavailable`. Do not bypass this guard. Native containment and cancellation have not been established.

`verify-run` checks unkeyed SHA-256 integrity only; it does not authenticate a producer or prove computational correctness. Quantum execution is classical statevector simulation. The Qiskit fixtures are scoped comparison data, not a security certification.

Report security issues privately to the repository owner before filing public details. The curated source tree is distributed under Apache-2.0; the software is experimental and is provided without warranty under that license. No support SLA or security warranty is offered.
