"""Link captured 8093 evidence into a new 8099B saved-run manifest."""
import hashlib, importlib.util, json, os, pathlib, re, uuid

ROOT = pathlib.Path(__file__).resolve().parent
STORE = ROOT / "native_evidence_8099b"
spec = importlib.util.spec_from_file_location("gate2_native_evidence", ROOT / "dependencies" / "8093" / "web_ide" / "native_evidence.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Gate 2 evidence module unavailable")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

def new_state(source):
    if not isinstance(source, str):
        return None
    return {"context": {"parent_id": uuid.uuid4().hex, "parent_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest()},
            "references": [], "errors": [], "attempted": 0}

def add_links(runs, run_id, state):
    if not re.fullmatch(r"[0-9]{8}T[0-9]{12}Z_[0-9a-f]{8}", run_id):
        raise ValueError("invalid saved-run identity")
    folder = pathlib.Path(runs) / run_id
    if folder.is_symlink() or not folder.is_dir() or folder.parent.resolve() != pathlib.Path(runs).resolve():
        raise ValueError("invalid saved-run directory")
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("invalid parent manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_names = [name for name in manifest.get("files_sha256", {}) if name.startswith("source.") and pathlib.PurePath(name).name == name]
    if len(source_names) != 1 or (folder / source_names[0]).is_symlink() or hashlib.sha256((folder / source_names[0]).read_bytes()).hexdigest() != state["context"]["parent_source_sha256"] or manifest["files_sha256"][source_names[0]] != state["context"]["parent_source_sha256"]:
        raise ValueError("parent source provenance mismatch")
    checked = []
    for ref in state["references"]:
        try:
            child_manifest = ev.verify(STORE, state["context"], ref)
            checked.append({"reference": ref, "integrity": "verified", "retention_status": child_manifest["retention_status"]})
        except (ev.EvidenceError, OSError, ValueError, KeyError) as exc:
            checked.append({"reference": ref, "integrity": "failed", "error": str(exc)})
    links = {"schema": 1, **state["context"], "attempted": state["attempted"], "executions": checked, "errors": state["errors"]}
    raw = (json.dumps(links, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path = folder / "native_evidence_links.json"
    with path.open("xb") as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    manifest["files_sha256"][path.name] = hashlib.sha256(raw).hexdigest()
    manifest["native_evidence_parent_id"] = state["context"]["parent_id"]
    manifest["native_evidence_parent_source_sha256"] = state["context"]["parent_source_sha256"]
    manifest["native_evidence_count"] = len(checked)
    manifest["native_evidence_integrity"] = ("verified" if checked and len(checked) == state["attempted"] and not state["errors"] and all(x["integrity"] == "verified" and x["retention_status"] == "complete" for x in checked) else "incomplete")
    temp = folder / (".manifest-" + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(temp, manifest_path)
    finally:
        if temp.exists(): temp.unlink()
    return manifest["native_evidence_integrity"]
