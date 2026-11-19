"""64-bit Win32 job lifetime and suspended process creation for the bounded runner."""
import ctypes as C
from ctypes import wintypes as W
import math
import subprocess
import sys
import time

K = C.WinDLL("kernel32", use_last_error=True)
PTR = C.c_void_p
SIZE = C.c_size_t
DWORD = W.DWORD


def api(name, result, *args):
    fn = getattr(K, name)
    fn.restype, fn.argtypes = result, args
    return fn


def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_int64), ("job_time", C.c_int64), ("flags", DWORD),
                ("working_min", SIZE), ("working_max", SIZE), ("active_limit", DWORD),
                ("affinity", SIZE), ("priority", DWORD), ("scheduling", DWORD)]


class Limits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", C.c_uint64*6), ("process_limit", SIZE),
                ("job_limit", SIZE), ("peak_process", SIZE), ("peak_job", SIZE)]


class Accounting(C.Structure):
    _fields_ = [("times", C.c_int64*4), ("faults", DWORD), ("total", DWORD),
                ("active", DWORD), ("terminated", DWORD)]


class Startup(C.Structure):
    _fields_ = [("cb", DWORD), ("strings", PTR*3), ("dimensions_and_flags", DWORD*8),
                ("show", W.WORD), ("reserved_bytes", W.WORD), ("reserved", PTR),
                ("standard_handles", PTR*3), ("attributes", PTR)]


class Process(C.Structure):
    _fields_ = [("process", PTR), ("thread", PTR), ("pid", DWORD), ("tid", DWORD)]


create_job = api("CreateJobObjectW", PTR, PTR, W.LPCWSTR)
set_job = api("SetInformationJobObject", W.BOOL, PTR, C.c_int, PTR, DWORD)
query_job = api("QueryInformationJobObject", W.BOOL, PTR, C.c_int, PTR, DWORD, PTR)
kill_job = api("TerminateJobObject", W.BOOL, PTR, DWORD)
close = api("CloseHandle", W.BOOL, PTR)
initialize = api("InitializeProcThreadAttributeList", W.BOOL, PTR, DWORD, DWORD, C.POINTER(SIZE))
update = api("UpdateProcThreadAttribute", W.BOOL, PTR, DWORD, SIZE, PTR, SIZE, PTR, PTR)
destroy = api("DeleteProcThreadAttributeList", None, PTR)
create = api("CreateProcessW", W.BOOL, W.LPCWSTR, W.LPWSTR, PTR, PTR, W.BOOL, DWORD,
             PTR, W.LPCWSTR, C.POINTER(Startup), C.POINTER(Process))
member = api("IsProcessInJob", W.BOOL, PTR, PTR, C.POINTER(W.BOOL))
resume = api("ResumeThread", DWORD, PTR)
wait = api("WaitForSingleObject", DWORD, PTR, DWORD)
exit_code = api("GetExitCodeProcess", W.BOOL, PTR, C.POINTER(DWORD))


class Job:
    def __init__(self, limit, *, inner_limit=None):
        if (C.sizeof(Limits), C.sizeof(Startup), C.sizeof(Process)) != (144, 112, 24):
            raise RuntimeError("unsupported Windows ABI")
        self.inner = None
        self.handle = checked(create_job(None, None))
        try:
            limits = Limits()
            limits.basic.flags = 0x2000 | 0x200  # KILL_ON_JOB_CLOSE | JOB_MEMORY
            limits.job_limit = limit
            checked(set_job(self.handle, 9, C.byref(limits), C.sizeof(limits)))
            readback = self.query(9, Limits)
            if readback.basic.flags != limits.basic.flags or readback.job_limit != limit:
                raise RuntimeError("job limit readback mismatch")
            if inner_limit is not None:
                self.inner = Job(inner_limit)
        except BaseException:
            checked(close(self.handle))
            raise

    def query(self, kind, structure):
        result = structure()
        checked(query_job(self.handle, kind, C.byref(result), C.sizeof(result), None))
        return result

    def launch(self, args, cwd):
        # JOB_LIST associates at creation, including if the supervisor dies before ResumeThread.
        size = SIZE()
        initialize(None, 1, 0, C.byref(size))
        if C.get_last_error() != 122 or not size.value:
            raise C.WinError(C.get_last_error())
        storage = C.create_string_buffer(size.value)
        checked(initialize(storage, 1, 0, C.byref(size)))
        try:
            chain = [self.handle] if self.inner is None else [self.handle, self.inner.handle]
            handles = (PTR*len(chain))(*chain)
            checked(update(storage, 0, 0x2000D, handles, C.sizeof(handles), None, None))
            startup = Startup()
            startup.cb = C.sizeof(startup)
            startup.attributes = C.cast(storage, PTR)
            process = Process()
            command = C.create_unicode_buffer(subprocess.list2cmdline([sys.executable, *map(str,args)]))
            # EXTENDED_STARTUPINFO_PRESENT | DETACHED_PROCESS | CREATE_SUSPENDED
            checked(create(sys.executable, command, None, None, False, 0x0008000C,
                           None, str(cwd), C.byref(startup), C.byref(process)))
            return process
        finally:
            destroy(storage)

    def run(self, args, cwd, deadline, stage):
        if time.monotonic() >= deadline:
            raise TimeoutError("deadline before launch")
        p = self.launch(args, cwd)
        try:
            verified = W.BOOL()
            for job in (self, self.inner):
                if job is not None:
                    checked(member(p.process, job.handle, C.byref(verified)))
                    if not verified.value:
                        raise RuntimeError("required job membership missing")
            stage.update(pid=p.pid, membership_verified=True)
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline before resume")
            if resume(p.thread) != 1:
                raise RuntimeError("unexpected suspended thread count")
            remaining = max(0, deadline-time.monotonic())
            result = wait(p.process, math.ceil(remaining*1000))
            if result == 258 or time.monotonic() >= deadline:
                raise TimeoutError("worker deadline")
            if result != 0:
                raise C.WinError(C.get_last_error())
            status = DWORD()
            checked(exit_code(p.process, C.byref(status)))
            stage["exit_status"] = status.value
            if status.value:
                raise ChildProcessError(status.value)
            # Windows can retire a console host just after the worker signals.
            drain_until = min(deadline, time.monotonic()+0.5)
            while self.query(1, Accounting).active:
                if time.monotonic() >= drain_until:
                    raise RuntimeError("live descendants after worker exit")
                time.sleep(.005)
            if time.monotonic() >= deadline:
                raise TimeoutError("deadline during job drain")
        finally:
            # Account for timeout and partial startup even if the process never ran.
            try:
                if wait(p.process, 0) != 0:
                    checked(kill_job(self.handle, 124))
                    if wait(p.process, 10000) != 0:
                        raise RuntimeError("worker termination unconfirmed")
                status = DWORD()
                checked(exit_code(p.process, C.byref(status)))
                stage["exit_status"] = status.value
            finally:
                try:
                    checked(close(p.thread))
                finally:
                    checked(close(p.process))

    def finish(self, report):
        try:
            checked(kill_job(self.handle, 125))
            end = time.monotonic()+10
            while True:
                counts = self.query(1, Accounting)
                report.update(active_after_cleanup=counts.active, total_processes=counts.total)
                if not counts.active:
                    break
                if time.monotonic() >= end:
                    raise RuntimeError("job termination unconfirmed")
                time.sleep(.005)
            report["peak_job_committed_bytes"] = self.query(9, Limits).peak_job
            if self.inner is not None:
                report["inner_peak_job_committed_bytes"] = self.inner.query(9, Limits).peak_job
        finally:
            try:
                if self.inner is not None:
                    checked(close(self.inner.handle))
            finally:
                checked(close(self.handle))
