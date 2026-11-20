"""Record Gate 4c native runs and independent Windows commit probes."""
import argparse
import ctypes as C
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
MODULE = "tools.high_support.audit_gate4c_native"
VERSION = "sharkbyte-xz-cx-h-candidate-v1"
TESTS = ["tests.test_h4_gate4c_containment", "tests.test_h4_compatibility",
         "tests.test_h4_historical_checkout"]
FILES = ("tools/high_support/h4_compatibility_contained.py",
         "tools/high_support/windows_job.py", "tools/high_support/h4_compatibility.py",
         "tools/high_support/h4_historical_checkout.py",
         "tools/high_support/audit_gate4c_native.py", "tests/test_h4_gate4c_containment.py",
         "tests/test_h4_compatibility.py", "tests/test_h4_historical_checkout.py",
         "evidence/h4-candidate/source.json", "evidence/h4-candidate/receipt.json")


def probe(size, method):
    from ctypes import wintypes as W
    kernel = C.WinDLL("kernel32", use_last_error=True)
    psapi = C.WinDLL("psapi", use_last_error=True)

    class Counters(C.Structure):
        _fields_ = [("cb", W.DWORD), ("faults", W.DWORD),
                    ("values", C.c_size_t * 9)]

    class Region(C.Structure):
        _fields_ = [("base", C.c_void_p), ("allocation", C.c_void_p),
                    ("allocation_protect", W.DWORD), ("partition", W.WORD),
                    ("size", C.c_size_t), ("state", W.DWORD),
                    ("protect", W.DWORD), ("type", W.DWORD)]

    kernel.GetCurrentProcess.restype = W.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (W.HANDLE, C.POINTER(Counters), W.DWORD)
    kernel.VirtualAlloc.argtypes = (C.c_void_p, C.c_size_t, W.DWORD, W.DWORD)
    kernel.VirtualAlloc.restype = C.c_void_p
    kernel.VirtualFree.argtypes = (C.c_void_p, C.c_size_t, W.DWORD)
    kernel.VirtualQuery.argtypes = (C.c_void_p, C.POINTER(Region), C.c_size_t)
    kernel.VirtualQuery.restype = C.c_size_t

    def current():
        counters = Counters()
        counters.cb = C.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), C.byref(counters), counters.cb):
            raise C.WinError(C.get_last_error())
        return counters.values[-1]  # PROCESS_MEMORY_COUNTERS_EX.PrivateUsage

    address = None
    if method == "virtualalloc":
        address = kernel.VirtualAlloc(None, size, 0x2000, 4)  # MEM_RESERVE
        if not address:
            raise C.WinError(C.get_last_error())
    try:
        before = current()
        error = None
        state = None
        if method == "virtualalloc":
            committed = kernel.VirtualAlloc(address, size, 0x1000, 4)  # MEM_COMMIT
            error = 0 if committed else C.get_last_error()
            region = Region()
            if kernel.VirtualQuery(address, C.byref(region), C.sizeof(region)) != C.sizeof(region):
                raise C.WinError(C.get_last_error())
            state = region.state
            if committed:
                C.c_ubyte.from_address(address + size - 1).value = 42
        else:
            try:
                allocation = bytearray(size)
                committed = True
            except MemoryError:
                committed = False
        after = current()
        return {"committed": bool(committed), "win32_error": error,
                "region_state": state, "private_usage_before": before,
                "private_usage_after": after}
    finally:
        if address and not kernel.VirtualFree(address, 0, 0x8000):
            raise C.WinError(C.get_last_error())


def matrix():
    from .windows_job import Job, Limits
    scenarios = [(cap, cap+32, nested, "virtualalloc", 10)
                 for cap in (48, 64, 96) for nested in (False, True)]
    scenarios += [(64, 96, True, "bytearray", 10), (64, 8, True, "virtualalloc", 10)]
    rows = []
    with tempfile.TemporaryDirectory(prefix="gate4c-probe-") as directory:
        for cap, request, nested, method, repeats in scenarios:
            for repetition in range(repeats):
                path = Path(directory)/f"{len(rows)}.json"
                mib = 1024**2
                job = Job(cap*mib, inner_limit=(cap-12)*mib if nested else None)
                stage, accounting = {}, {}
                try:
                    limits = [j.query(9, Limits) for j in (job, job.inner) if j is not None]
                    job.run(["-B", "-E", "-s", "-m", MODULE, "--probe",
                             str(request*mib), method, str(path)], ROOT, time.monotonic()+10, stage)
                finally:
                    job.finish(accounting)
                sample = json.loads(path.read_bytes())
                control = request < cap
                if (sample["committed"] != control or accounting["active_after_cleanup"] != 0
                        or (method == "virtualalloc" and sample["region_state"] !=
                            (0x1000 if control else 0x2000))):
                    raise RuntimeError(f"unexpected allocation or cleanup: {sample}, {accounting}")
                rows.append(dict(sample, repetition=repetition+1, method=method,
                                 request_bytes=request*mib, stage=stage, accounting=accounting,
                                 limits=[{"bytes": x.job_limit, "flags": x.basic.flags} for x in limits]))
    return rows


def native():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    hashes = {}
    for name in FILES:
        raw = (ROOT/name).read_bytes()
        expected = subprocess.check_output(["git", "show", f"{revision}:{name}"], cwd=ROOT)
        if name.endswith(".py"):
            raw = raw.replace(b"\r\n", b"\n")
        if raw != expected:
            raise ValueError("working file differs from tested revision: "+name)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    commands = []
    for flags in ([], ["-O"], ["-OO"]):
        commands.append(["-B", *flags, "-m", "unittest", *TESTS])
    inputs = [VERSION, "evidence/h4-candidate/source.json", "evidence/h4-candidate/receipt.json"]
    commands.append(["-B", "-m", "tools.high_support.h4_compatibility_contained", *inputs, *inputs])
    runs = []
    for command in commands:
        result = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True,
                                text=True, timeout=180)
        runs.append({"arguments": command, "exit_code": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            raise RuntimeError(runs[-1])
    return {"tested_commit": revision, "sha256": hashes, "python": sys.version,
            "platform": platform.platform(), "machine": platform.machine(), "runs": runs,
            "windows_probe_matrix": matrix() if sys.platform == "win32" else []}


def main():
    if len(sys.argv) == 5 and sys.argv[1] == "--probe":
        Path(sys.argv[4]).write_text(json.dumps(probe(int(sys.argv[2]), sys.argv[3])), encoding="ascii")
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = native()
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
