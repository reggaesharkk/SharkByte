"""Resource-bounded asynchronous manager for Studio's 16-million-state run."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SCALING_SCRIPT = ROOT / "benchmarks" / "sb_quantum_benchmark" / "support_scaling.py"
STATES = 1 << 24
PROCESS_MEMORY_LIMIT_BYTES = int(3.25 * 1024**3)
AVAILABLE_MEMORY_RESERVE_BYTES = 1 * 1024**3
MIN_AVAILABLE_MEMORY_BYTES = PROCESS_MEMORY_LIMIT_BYTES + AVAILABLE_MEMORY_RESERVE_BYTES
TIMEOUT_SECONDS = 90.0
POLL_SECONDS = 0.10


class StudioResourceRefusal(RuntimeError):
    def __init__(self, message, *, available_bytes=None, required_bytes=None):
        super().__init__(message)
        self.available_bytes = available_bytes
        self.required_bytes = required_bytes


def available_memory_bytes() -> int:
    """Read OS-available physical memory; fail closed if it is unavailable."""
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("Windows could not report available physical memory")
        return int(status.ullAvailPhys)
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except ImportError as exc:
        raise OSError("OS available-memory reporting is unavailable") from exc


class _JobIoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _JobBasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_ulong),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_ulong),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_ulong),
        ("SchedulingClass", ctypes.c_ulong),
    ]


class _JobExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimit),
        ("IoInfo", _JobIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _WindowsJob:
    """Windows Job Object providing a hard per-process memory ceiling."""

    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x100
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

    def __init__(self, process, memory_limit_bytes):
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self._kernel.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
        self._kernel.SetInformationJobObject.restype = ctypes.c_int
        self._kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._kernel.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel.QueryInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        self._kernel.QueryInformationJobObject.restype = ctypes.c_int
        self._kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self._kernel.TerminateJobObject.restype = ctypes.c_int
        self._kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel.CloseHandle.restype = ctypes.c_int
        self._handle = self._kernel.CreateJobObjectW(None, None)
        if not self._handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = _JobExtendedLimit()
        info.BasicLimitInformation.LimitFlags = (
            self.JOB_OBJECT_LIMIT_PROCESS_MEMORY | self.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info.ProcessMemoryLimit = memory_limit_bytes
        if not self._kernel.SetInformationJobObject(
                self._handle, self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        if not self._kernel.AssignProcessToJobObject(
                self._handle, ctypes.c_void_p(int(process._handle))):
            self.close()
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

    def peak_memory_bytes(self):
        info = _JobExtendedLimit()
        ok = self._kernel.QueryInformationJobObject(
            self._handle, self.JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info), ctypes.sizeof(info), None)
        if not ok:
            return 0
        return int(max(info.PeakProcessMemoryUsed, info.PeakJobMemoryUsed))

    def terminate(self, code=1):
        if self._handle:
            self._kernel.TerminateJobObject(self._handle, code)

    def close(self):
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None


def _linux_peak_rss_bytes(pid):
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
        values = {}
        for line in status.splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                key, value = line.split(":", 1)
                values[key] = int(value.split()[0]) * 1024
        return values.get("VmHWM", values.get("VmRSS", 0))
    except (OSError, ValueError, IndexError):
        return 0


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _git_revision_and_clean():
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=3).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=3).strip())
        return revision, not dirty
    except (OSError, subprocess.SubprocessError):
        return None, False


def _record_preview(record):
    result = record["result"]
    if len(json.dumps(record)) <= 64 * 1024:
        return record
    # Large statevectors are never expected here; keep the response bounded anyway.
    return {**record, "result": {k: v for k, v in result.items()
                                  if k not in ("probabilities", "amplitudes")},
            "result_preview": True}


class ScalingJobManager:
    """Runs one fixed, resource-limited 16M benchmark asynchronously."""

    def __init__(self, receipt_dir, receipts, *, memory_provider=None,
                 timeout_seconds=TIMEOUT_SECONDS, process_memory_limit_bytes=PROCESS_MEMORY_LIMIT_BYTES,
                 minimum_available_memory_bytes=MIN_AVAILABLE_MEMORY_BYTES,
                 command_builder=None, process_limiter=None):
        self.receipt_dir = Path(receipt_dir)
        self.receipts = receipts
        self.memory_provider = memory_provider or available_memory_bytes
        self.timeout_seconds = float(timeout_seconds)
        self.process_memory_limit_bytes = int(process_memory_limit_bytes)
        self.minimum_available_memory_bytes = int(minimum_available_memory_bytes)
        self.command_builder = command_builder or self._command
        self.process_limiter = process_limiter
        self._lock = threading.RLock()
        self._jobs = {}

    def _command(self, progress_path):
        worker = ROOT / "tools" / "studio_scaling_worker.py"
        return [sys.executable, "-B", str(worker),
                str(self.process_memory_limit_bytes), str(STATES), str(progress_path)]

    def start(self, source):
        try:
            available = int(self.memory_provider())
        except OSError as exc:
            raise StudioResourceRefusal(
                f"Could not check available memory; refusing the 16,777,216-state run: {exc}",
                required_bytes=self.minimum_available_memory_bytes) from exc
        if available < self.minimum_available_memory_bytes:
            raise StudioResourceRefusal(
                "16,777,216-state run refused: available physical memory is below the configured safety reserve.",
                available_bytes=available, required_bytes=self.minimum_available_memory_bytes)
        with self._lock:
            if any(job["status"] in ("starting", "running", "cancelling")
                   for job in self._jobs.values()):
                raise StudioResourceRefusal("A large Studio benchmark is already active.")
            execution_id = uuid4().hex
            progress_path = self.receipt_dir / f"{execution_id}.progress.jsonl"
            job = {
                "execution_id": execution_id, "source": source,
                "status": "starting", "phase": "starting", "started": time.monotonic(),
                "available_memory_bytes": available, "peak_memory_bytes": 0,
                "process_memory_limit_bytes": self.process_memory_limit_bytes,
                "gate_index": 0, "gate_count": 0, "active_states": 1,
                "progress_path": progress_path, "progress_offset": 0,
                "error": None, "record": None, "receipt_url": None,
                "cancel_requested": False, "process": None, "limiter": None,
            }
            self._jobs[execution_id] = job
            launch_started = time.perf_counter()
            kwargs = {"cwd": ROOT, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                      "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                kwargs["start_new_session"] = True
            try:
                process = subprocess.Popen(self.command_builder(progress_path), **kwargs)
                job["process"] = process
                job["startup_seconds"] = time.perf_counter() - launch_started
                if self.process_limiter is not None:
                    job["limiter"] = self.process_limiter(process, self.process_memory_limit_bytes)
                elif os.name == "nt":
                    job["limiter"] = _WindowsJob(process, self.process_memory_limit_bytes)
            except Exception as exc:
                process = job.get("process")
                if process and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                self._jobs.pop(execution_id, None)
                raise StudioResourceRefusal(
                    f"Could not start the bounded benchmark worker safely: {exc}") from exc
            job["status"] = "running"
            job["phase"] = "loading"
            threading.Thread(target=self._monitor, args=(execution_id,),
                             name=f"sharkbyte-scaling-{execution_id[:8]}", daemon=True).start()
            return execution_id

    def _read_progress(self, job):
        path = job["progress_path"]
        try:
            with path.open("rb") as stream:
                stream.seek(job["progress_offset"])
                data = stream.read()
                job["progress_offset"] += len(data)
        except OSError:
            return
        for line in data.splitlines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            job["phase"] = event.get("phase", job["phase"])
            job["gate_index"] = int(event.get("gate_index", job["gate_index"]))
            job["gate_count"] = int(event.get("gate_count", job["gate_count"]))
            job["active_states"] = int(event.get("active_states", job["active_states"]))

    def _memory_peak(self, job):
        limiter = job.get("limiter")
        if limiter is not None and hasattr(limiter, "peak_memory_bytes"):
            return int(limiter.peak_memory_bytes())
        process = job.get("process")
        if process is not None and os.name != "nt":
            return int(_linux_peak_rss_bytes(process.pid))
        return 0

    def _terminate(self, job):
        limiter = job.get("limiter")
        process = job.get("process")
        if limiter is not None and hasattr(limiter, "terminate"):
            try:
                limiter.terminate(1)
            except Exception:
                pass
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass

    def _attach_provenance(self, job, result, peak_memory, elapsed):
        benchmark_path = str(SCALING_SCRIPT.parent)
        if benchmark_path not in sys.path:
            sys.path.insert(0, benchmark_path)
        from support_scaling import build_circuit
        circuit, source_hash, added, source_path = build_circuit(STATES)
        gates = [list(gate) for gate in circuit.gates]
        circuit_identity = {
            "name": circuit.name, "qubits": circuit.qubits,
            "gate_count": len(gates), "gates": gates,
            "base_source_sha256": source_hash,
        }
        circuit_identity["sha256"] = _sha256(_canonical(circuit_identity))
        references = []
        reference_paths = (
            ROOT / "benchmarks" / "sb_quantum_benchmark" / "scaling-16777216-cirq.json",
            ROOT / "evidence" / "windows-arm64-cirq" / "cirq-16777216.json",
        )
        for path in reference_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (payload.get("status") != "PASS" or payload.get("qubits") != circuit.qubits
                    or payload.get("gates") != len(gates)
                    or payload.get("source_sha256") != source_hash
                    or payload.get("added_gates") != [list(gate) for gate in added]
                    or payload.get("reference_active_states") != STATES
                    or payload.get("compared_amplitudes") != STATES):
                raise ValueError(f"Archived independent reference does not match current circuit: {path.name}")
            references.append({
                "kind": "independent Cirq full-statevector comparison",
                "receipt_path": path.relative_to(ROOT).as_posix(),
                "receipt_sha256": _sha256(path.read_bytes()),
                "reference_revision": payload.get("revision"),
                "cirq_core": payload.get("cirq_core"),
                "maximum_amplitude_error": payload.get("max_complex_amplitude_error"),
                "amplitude_tolerance": payload.get("amplitude_tolerance"),
                "matched_source_sha256": source_hash,
                "matched_circuit_sha256": circuit_identity["sha256"],
            })
        source_revision, source_tree_clean = _git_revision_and_clean()
        implementation_paths = {
            "studio_server": ROOT / "sharkbyte_studio.py",
            "scaling_runner": SCALING_SCRIPT,
            "sparse_backend": ROOT / "benchmarks" / "sb_quantum_benchmark" / "sparse_backend.py",
            "frontier_parser": ROOT / "benchmarks" / "sb_quantum_benchmark" / "frontier30.py",
            "resource_limited_worker": ROOT / "tools" / "studio_scaling_worker.py",
        }
        result["circuit_identity"] = circuit_identity
        result["verification"] = {
            "status": result["status"],
            "method": "exact populated-state count and probability checks against the uniform analytic distribution; circuit identity also matches archived independent Cirq full-statevector receipts",
            "populated_state_count_pass": result["final_active_states"] == STATES,
            "peak_state_count_pass": result["peak_active_states"] == STATES,
            "normalization_pass": abs(result["probability_sum"] - 1.0) <= 1e-12,
            "uniform_probability_pass": result["max_uniform_probability_error"] <= (1 / STATES) * 1e-12,
            "independent_reference_receipts": references,
        }
        result["studio_execution"] = {
            "execution_id": job["execution_id"],
            "worker_wall_seconds": elapsed,
            "worker_startup_seconds": job.get("startup_seconds"),
            "process_peak_memory_bytes": peak_memory,
            "memory_measurement": "Windows Job Object peak process memory" if os.name == "nt" else "Linux /proc VmHWM peak RSS",
            "resource_limits": {
                "timeout_seconds": self.timeout_seconds,
                "process_memory_limit_bytes": self.process_memory_limit_bytes,
                "minimum_available_memory_bytes": self.minimum_available_memory_bytes,
                "preflight_available_memory_bytes": job["available_memory_bytes"],
            },
            "environment": {
                "platform": platform.platform(), "system": platform.system(),
                "machine": platform.machine(), "processor": platform.processor(),
                "python": platform.python_version(), "cpu_count": os.cpu_count(),
            },
            "source_revision": source_revision,
            "source_tree_clean_at_launch": source_tree_clean,
            "implementation_sha256": {
                name: _sha256(path.read_bytes()) for name, path in implementation_paths.items()
            },
            "reference_receipt_paths": [item["receipt_path"] for item in references],
        }
        result["result_sha256"] = _sha256(_canonical({k: v for k, v in result.items()
                                                       if k != "result_sha256"}))
        return result

    def _monitor(self, execution_id):
        with self._lock:
            job = self._jobs[execution_id]
            process = job["process"]
        while True:
            with self._lock:
                self._read_progress(job)
                job["peak_memory_bytes"] = max(job["peak_memory_bytes"], self._memory_peak(job))
                job["elapsed_seconds"] = time.monotonic() - job["started"]
                cancelled = job["cancel_requested"]
                timed_out = job["elapsed_seconds"] >= self.timeout_seconds
            if cancelled or timed_out:
                self._terminate(job)
                try:
                    process.communicate(timeout=2)
                except (OSError, subprocess.SubprocessError):
                    pass
                with self._lock:
                    job["status"] = "cancelled" if cancelled else "timed_out"
                    job["phase"] = job["status"]
                    job["error"] = ("Run cancelled by user; worker process was terminated and its memory released."
                                     if cancelled else
                                     f"Run exceeded the {self.timeout_seconds:g}-second limit; worker was terminated.")
                break
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                with self._lock:
                    job["peak_memory_bytes"] = max(job["peak_memory_bytes"], self._memory_peak(job))
                    job["elapsed_seconds"] = time.monotonic() - job["started"]
                    if process.returncode != 0:
                        job["status"] = "failed"
                        job["phase"] = "failed"
                        job["error"] = stderr.strip() or stdout.strip() or f"Worker exited with code {process.returncode}."
                    else:
                        try:
                            result = json.loads(stdout)
                            result = self._attach_provenance(
                                job, result, job["peak_memory_bytes"], job["elapsed_seconds"])
                            from sharkbyte_alpha.cli import envelope
                            record = envelope(job["source"], "scaling_16m", result)
                            path = self.receipt_dir / f"{execution_id}.json"
                            with path.open("x", encoding="utf-8", newline="\n") as receipt:
                                json.dump(record, receipt, sort_keys=True, ensure_ascii=True,
                                          indent=2, allow_nan=False)
                                receipt.write("\n")
                            self.receipts[execution_id] = path
                            if len(self.receipts) > 4:
                                oldest = next(iter(self.receipts))
                                self.receipts.pop(oldest).unlink(missing_ok=True)
                            job["record"] = record
                            job["receipt_url"] = f"/receipts/{execution_id}.json"
                            job["status"] = "completed" if result["status"] == "PASS" else "failed"
                            job["phase"] = job["status"]
                            if job["status"] == "failed":
                                job["error"] = "Analytical verification checks failed; no PASS result was issued."
                        except Exception as exc:
                            job["status"] = "failed"
                            job["phase"] = "failed"
                            job["error"] = f"Could not verify or store the worker result: {type(exc).__name__}: {exc}"
                break
            time.sleep(POLL_SECONDS)
        with self._lock:
            job["peak_memory_bytes"] = max(job["peak_memory_bytes"], self._memory_peak(job))
            job["elapsed_seconds"] = time.monotonic() - job["started"]
            limiter = job.get("limiter")
            if limiter is not None and hasattr(limiter, "close"):
                limiter.close()
            job["limiter"] = None
            job["process"] = None
            job["progress_path"].unlink(missing_ok=True)

    def cancel(self, execution_id):
        with self._lock:
            job = self._jobs.get(execution_id)
            if job is None:
                return None
            if job["status"] in ("starting", "running"):
                job["cancel_requested"] = True
                job["status"] = "cancelling"
                job["phase"] = "cancelling"
            return self._snapshot(job)

    def snapshot(self, execution_id):
        with self._lock:
            job = self._jobs.get(execution_id)
            return None if job is None else self._snapshot(job)

    @staticmethod
    def _snapshot(job):
        value = {
            "execution_id": job["execution_id"], "status": job["status"],
            "phase": job["phase"], "gate_index": job["gate_index"],
            "gate_count": job["gate_count"], "active_states": job["active_states"],
            "elapsed_seconds": job.get("elapsed_seconds", time.monotonic() - job["started"]),
            "peak_memory_bytes": job["peak_memory_bytes"],
            "process_memory_limit_bytes": job.get("process_memory_limit_bytes", PROCESS_MEMORY_LIMIT_BYTES),
            "error": job["error"], "receipt_url": job["receipt_url"],
        }
        if job["record"] is not None:
            value["record"] = _record_preview(job["record"])
        if job["status"] == "refused":
            value["available_memory_bytes"] = job.get("available_memory_bytes")
        return value

    def shutdown(self):
        with self._lock:
            active = [job for job in self._jobs.values()
                      if job["status"] in ("starting", "running", "cancelling")]
            for job in active:
                job["cancel_requested"] = True
                job["status"] = "cancelling"
        for job in active:
            self._terminate(job)
