"""Bounded evidence capture for 8099B's isolated 8093 worker.

Only fixed job-relative files are copied. This is diagnostic evidence; it does
not imply that execution, native matching, or process cancellation succeeded.
"""
from __future__ import annotations
import hashlib, json, os, pathlib, re, threading, uuid
from datetime import datetime, timezone

ID = re.compile(r"^[0-9a-f]{32}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
LIMIT = 8 * 1024 * 1024
TOTAL_LIMIT = 200 * 1024 * 1024
LOCK = threading.Lock()
FILES = {
    "direct_native": {"assembly.S": "direct/program.S", "program.elf": "direct/program.elf", "elf.disassembly.txt": "direct/elf.disassembly.txt", "runtime.stdout.bin": "direct/stdout.bin", "runtime.stderr.bin": "direct/stderr.bin", "runtime.time.txt": "direct/time.txt", "disassembly.stderr.txt": "direct/elf.disassembly.stderr.txt"},
    "native_interpreter": {"interpreter.elf": "native/request.interpreter.elf", "interpreter.program.c": "native/request.interpreter.program.c", "runtime.stdout.bin": "native/request.interpreter.stdout.bin", "runtime.stderr.bin": "native/request.interpreter.stderr.bin", "runtime.time.txt": "native/request.interpreter.time.txt", "interpreter.build.json": "native/request.interpreter.json"},
}

class EvidenceError(Exception):
    pass

def digest(data):
    return hashlib.sha256(data).hexdigest()

def validate_context(context):
    if not isinstance(context, dict) or set(context) != {"parent_id", "parent_source_sha256"}:
        raise EvidenceError("invalid evidence context")
    if not isinstance(context["parent_id"], str) or not ID.fullmatch(context["parent_id"]):
        raise EvidenceError("invalid parent id")
    if not isinstance(context["parent_source_sha256"], str) or not SHA.fullmatch(context["parent_source_sha256"]):
        raise EvidenceError("invalid parent source hash")
    return context

def _usage(store):
    total = 0
    for root, dirs, files in os.walk(store, followlinks=False):
        for name in dirs + files:
            p = pathlib.Path(root) / name
            if p.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(p)):
                raise EvidenceError("link in evidence store")
        for name in files:
            total += (pathlib.Path(root) / name).stat().st_size
            if total > TOTAL_LIMIT:
                raise EvidenceError("evidence store limit reached")
    return total

def capture(store, context, execution_id, backend, source, result, job_dir, worker_stdout=b"", worker_stderr=b""):
    validate_context(context)
    if not isinstance(execution_id, str) or not ID.fullmatch(execution_id) or backend not in FILES:
        raise EvidenceError("invalid execution identity or backend")
    if not isinstance(source, bytes) or len(source) > 65536:
        raise EvidenceError("invalid source")
    if not isinstance(result, dict):
        raise EvidenceError("invalid execution result")
    if result.get("execution_id") not in (None, execution_id):
        raise EvidenceError("execution identity mismatch")
    if result.get("source_sha256") not in (None, digest(source)):
        raise EvidenceError("source hash mismatch")
    store, job_dir = pathlib.Path(store), pathlib.Path(job_dir)
    if not job_dir.is_dir() or job_dir.is_symlink():
        raise EvidenceError("invalid job directory")
    job_root = job_dir.resolve(strict=True)
    payload = {"source.sb": source, "worker.stdout.bin": worker_stdout, "worker.stderr.bin": worker_stderr,
               "execution.json": (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")}
    missing = []
    for name, relative in FILES[backend].items():
        p = job_dir / relative
        if not p.exists():
            missing.append(name)
            continue
        if p.is_symlink() or not p.is_file() or not p.resolve(strict=True).is_relative_to(job_root):
            raise EvidenceError("unsafe job artifact: " + name)
        if p.stat().st_size > LIMIT:
            raise EvidenceError("artifact too large: " + name)
        payload[name] = p.read_bytes()
    if any(not isinstance(v, bytes) or len(v) > LIMIT for v in payload.values()) or sum(map(len, payload.values())) > LIMIT:
        raise EvidenceError("per-execution evidence limit exceeded")
    expected = {"direct_native": ("assembly.S", "program.elf", "elf.disassembly.txt"), "native_interpreter": ("interpreter.elf", "interpreter.program.c")}[backend]
    artifact_missing = [x for x in expected if x not in payload]
    if backend == "direct_native" and result.get("elf_disassembly_truncated"):
        artifact_missing.append("elf.disassembly.txt (truncated)")
    native = result.get("native") if isinstance(result.get("native"), dict) else {}
    exit_status = result.get("exit_status") if result.get("exit_status") is not None else native.get("exit_status")
    build_status = result.get("compile_exit_status") if result.get("compile_exit_status") is not None else native.get("build_exit_status")
    metadata = {"schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(), "execution_id": execution_id,
                "parent_id": context["parent_id"], "parent_source_sha256": context["parent_source_sha256"],
                "source_sha256": digest(source), "backend": backend, "execution_status": result.get("execution_status"),
                "native_exit_status": exit_status, "native_build_exit_status": build_status,
                "native_outcome": ("exit_zero" if exit_status == 0 else "exit_nonzero" if isinstance(exit_status, int) else "not_recorded"),
                "termination_reason": result.get("termination_reason"), "missing_artifacts": missing,
                "required_artifacts_missing": artifact_missing,
                "unavailable_by_backend": (["compiler-generated assembly and native disassembly are not generated by the interpreter backend"] if backend == "native_interpreter" else []),
                "elf_machine": result.get("elf_machine") if backend == "direct_native" else (result.get("native") or {}).get("elf_machine"),
                "retention_status": "complete" if not artifact_missing else "incomplete",
                "files": {k: {"bytes": len(v), "sha256": digest(v)} for k, v in sorted(payload.items())}}
    disassembly_hash = None if result.get("elf_disassembly_truncated") else result.get("elf_disassembly_sha256")
    for fname, reported in (("program.elf", result.get("elf_sha256")), ("assembly.S", result.get("assembly_sha256")), ("interpreter.elf", native.get("executable_sha256")), ("elf.disassembly.txt", disassembly_hash)):
        if fname in payload and reported is not None and digest(payload[fname]) != reported:
            raise EvidenceError("reported artifact hash mismatch: " + fname)
    manifest = (json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    with LOCK:
        store.mkdir(parents=True, exist_ok=True)
        if store.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(store)):
            raise EvidenceError("invalid evidence store")
        # mkdir is atomic across separate 8093 server processes. A stale lock
        # fails closed; it is never guessed safe to remove automatically.
        store_lock = store / ".gate2-write-lock"
        try:
            store_lock.mkdir()
        except FileExistsError as exc:
            raise EvidenceError("evidence store lock busy or stale") from exc
        try:
            if _usage(store) + sum(map(len, payload.values())) + len(manifest) > TOTAL_LIMIT:
                raise EvidenceError("evidence store limit reached")
            parent = store / context["parent_id"]
            parent.mkdir(exist_ok=True)
            if parent.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(parent)):
                raise EvidenceError("invalid parent evidence directory")
            final = parent / execution_id
            if final.exists():
                raise EvidenceError("evidence identity already exists")
            stage = parent / (".stage-" + uuid.uuid4().hex)
            stage.mkdir()
            try:
                for name, data in payload.items():
                    with (stage / name).open("xb") as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())
                with (stage / "manifest.json").open("xb") as f:
                    f.write(manifest)
                    f.flush()
                    os.fsync(f.fileno())
                os.rename(stage, final)
            except BaseException:
                # Preserve a partial stage for inspection; never silently delete it.
                raise
        finally:
            store_lock.rmdir()
    return {"parent_id": context["parent_id"], "parent_source_sha256": context["parent_source_sha256"],
            "execution_id": execution_id, "manifest_sha256": digest(manifest),
            "retention_status": metadata["retention_status"], "required_artifacts_missing": artifact_missing}

def verify(store, context, reference):
    validate_context(context)
    if not isinstance(reference, dict) or reference.get("parent_id") != context["parent_id"] or reference.get("parent_source_sha256") != context["parent_source_sha256"]:
        raise EvidenceError("parent reference mismatch")
    eid = reference.get("execution_id")
    if not isinstance(eid, str) or not ID.fullmatch(eid):
        raise EvidenceError("invalid evidence identity")
    folder = pathlib.Path(store) / context["parent_id"] / eid
    if pathlib.Path(store).is_symlink() or folder.parent.is_symlink() or folder.is_symlink() or not folder.is_dir() or not folder.resolve().is_relative_to(pathlib.Path(store).resolve()):
        raise EvidenceError("evidence missing")
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file() or manifest_path.stat().st_size > LIMIT:
        raise EvidenceError("invalid evidence manifest")
    raw = manifest_path.read_bytes()
    if digest(raw) != reference.get("manifest_sha256"):
        raise EvidenceError("manifest hash mismatch")
    manifest = json.loads(raw.decode("utf-8"))
    if manifest.get("execution_id") != eid or manifest.get("parent_id") != context["parent_id"] or manifest.get("parent_source_sha256") != context["parent_source_sha256"]:
        raise EvidenceError("manifest provenance mismatch")
    if not isinstance(manifest.get("files"), dict):
        raise EvidenceError("invalid evidence file inventory")
    for name, entry in manifest["files"].items():
        if pathlib.PurePath(name).name != name or name in ("", ".", ".."):
            raise EvidenceError("invalid artifact name")
        p = folder / name
        if p.is_symlink() or not p.is_file() or p.stat().st_size > LIMIT or not isinstance(entry, dict):
            raise EvidenceError("artifact missing: " + name)
        data = p.read_bytes()
        if len(data) != entry.get("bytes") or digest(data) != entry.get("sha256"):
            raise EvidenceError("artifact integrity failure: " + name)
    if "source.sb" not in manifest.get("files", {}) or manifest["files"]["source.sb"].get("sha256") != manifest.get("source_sha256"):
        raise EvidenceError("source provenance mismatch")
    return manifest
