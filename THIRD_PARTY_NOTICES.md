# Third-party notices

## Included software

The curated SharkByte package has no third-party Python runtime dependencies and does not bundle Qiskit, OpenQASM3 parser libraries, native toolchains, or external simulator implementations. The eight 8093–8099B source and pin files historically identified as vendored in `docs/RIGHTS_CLEARANCE_STATUS_20261112.md` are SharkByte project material; the owner attestation and file-level provenance basis for Apache-2.0 is recorded in `docs/APACHE_RIGHTS_CLEARANCE_20261112.md`. The 47 quantum fixture/reference records are project-generated validation material, not copied Qiskit implementation code.

## External build and validation tools (not redistributed)

The following software was used in build/test environments but is not included in this repository's source or runtime package:

- setuptools 84.2.0 (PEP 517 build backend; pinned in `pyproject.toml` and `BUILD_REQUIREMENTS.txt`)
- `build` 1.2.2.post1, `packaging` 24.2, `pyproject_hooks` 1.2.0, `colorama` 0.4.6 (isolated build wheelhouse only)
- Qiskit 2.6.2, OpenQASM3 1.0.1, and `qiskit-qasm3-import` 0.6.0 (independent Ubuntu validation environment only)
- GitHub-hosted `actions/checkout` and `actions/setup-python` (CI services/actions, not vendored)

These tools remain under their own distribution licenses and terms. Their use does not imply that SharkByte includes or is endorsed by those projects. Refer to each upstream distribution for its applicable license and notices.
