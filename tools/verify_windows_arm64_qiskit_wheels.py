import hashlib
import json
from pathlib import Path
import platform
import struct
import sys
import zipfile

WHEELHOUSE = Path(sys.argv[1])
if platform.machine() != "ARM64" or sys.platform != "win32":
    raise RuntimeError("Run with native Windows ARM64 Python")

wheel_evidence = {}
for package in ("qiskit", "rustworkx"):
    wheel, = WHEELHOUSE.glob(f"{package}-*-win_arm64.whl")
    with zipfile.ZipFile(wheel) as archive:
        modules = [name for name in archive.namelist() if name.endswith(".pyd")]
        if not modules:
            raise RuntimeError(f"No native modules in {wheel.name}")
        for name in modules:
            data = archive.read(name)
            offset = struct.unpack_from("<I", data, 0x3C)[0]
            if data[:2] != b"MZ" or data[offset:offset+6] != b"PE\0\0\x64\xaa":
                raise RuntimeError(f"Expected native ARM64 PE machine in {name}")
    wheel_evidence[package] = dict(file=wheel.name,
                                   sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
                                   pe_machine="0xAA64", native_modules=modules)
print(json.dumps(dict(host=platform.platform(), architecture=platform.machine(),
                      python=platform.python_version(), wheels=wheel_evidence), indent=2))
