# Third-party notices

## Included software

The curated runtime has no third-party Python runtime dependencies. The
historically vendored 8093–8099B Python snapshots and pin files are
SharkByte project material, as recorded in the earlier owner-attested rights
inventory and the current [Apache rights record](docs/APACHE_RIGHTS_CLEARANCE_20261114.md).
The checked-in quantum fixtures and probability records are project-created
validation material, not copied Qiskit implementation code.

## External build and validation tools (not redistributed)

The following tools or services were used in development or validation
environments. Their implementation code is not bundled here:

- setuptools 84.2.0 (PEP 517 build backend, pinned by this project)
- build, packaging, pyproject_hooks, and colorama (isolated build environment)
- Qiskit 2.6.2, OpenQASM3 1.0.1, and qiskit-qasm3-import 0.6.0 (independent validation environment)
- GitHub-hosted Actions used by the workflow

These tools remain subject to their own distribution licenses and terms. Their
use does not imply that SharkByte includes or is endorsed by those projects.
