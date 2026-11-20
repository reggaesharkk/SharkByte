# Gate 4c native evidence manifest

- [Windows ARM64 results and raw 80-row matrix](windows-commit-audit.json)
- [Ubuntu WSL2 ARM64 results](wsl-final-audit.json)
- [Earlier hostile review record](validation.json), preserved unchanged.

Both new records bind implementation, tests and canonical fixture bytes to tested commit 0e6655cd4166ab99b91c1bbcf87fb4bde04173aa. The publication commit adds these records and documentation only. Each record lists interpreter/platform, exact subprocess argument vectors and exit outcomes. The matrix records the configured/read-back outer and inner limits, flags, job peak accounting, process PrivateUsage before and after, refusal or commitment, Win32 error and post-cleanup process counts.

Reproduce from the tested commit with full Git history:

    python -B -m tools.high_support.audit_gate4c_native NEW-OUTPUT.json

On native Windows ARM64 this runs six VirtualAlloc refusal cases (48/64/96 MiB outer caps, single and nested jobs), the original nested bytearray refusal case, and an 8 MiB successful control. Each case repeats ten times. Native Windows reported flags 0x2200 throughout. Allocation tests use one allocation worker; descendant cleanup is exercised independently by the three test-mode runs.

| Criterion | Decision |
| --- | --- |
| Pinned v1 comparison, byte integrity and four outcome categories | PASS in tested conditions |
| Native focused suites | PASS: 29 in each of normal, -O and -OO on both ARM64 hosts |
| Allocation refusal and fail-closed over-cap telemetry | PASS: 70 refused allocations, unchanged policy |
| Direct commit cross-check | PASS: all 60 over-cap direct requests returned 1455, left MEM_RESERVE and had zero sampled PrivateUsage delta. All ten controls returned MEM_COMMIT and increased PrivateUsage by 8,404,992 bytes |
| Strict Windows reported-peak ceiling | FAIL: 70/70 refusal trials reported peaks above the outer cap. At 64 MiB the nested bytearray case reported 112,074,752 to 112,238,592 bytes |
| Worker timeout and descendant cleanup | PASS for the tested processes. All 80 matrix jobs reached zero active processes |
| Exact kernel accounting sequence and continuous aggregate live peak | OPEN. Process samples are point observations, not a job-wide high-water bound |
| Linux aggregate memory, escaped descendants, hostile filesystem races and authentication | OPEN |
| Research-only comparator | PASS within the documented trusted-code scope |
| Strict resource-containment acceptance | FAIL |
