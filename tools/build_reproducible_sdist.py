#!/usr/bin/env python3
"""Build a PEP 517 sdist, then repack it with normalized archive metadata.

The PEP 517 build remains isolated. The caller supplies a wheelhouse so both
the front end and the isolated setuptools backend can be resolved offline.
Only regular files and directories are accepted from setuptools' output.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import BinaryIO

PINNED_BUILD = "1.2.2.post1"
DEFAULT_EPOCH = 946684800  # 2000-01-01 UTC


def sha256(path: pathlib.Path) -> tuple[int, str]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            h.update(block)
    return size, h.hexdigest()


def _safe_member_name(name: str, is_directory: bool = False) -> None:
    if not name or "\x00" in name or "\\" in name:
        raise ValueError(f"unsafe archive member path: {name!r}")
    # Tar archives commonly spell directory entries with one trailing slash.
    # Normalize only that spelling; reject aliases such as repeated separators
    # and explicit dot segments so distinct headers cannot target one path.
    canonical = name[:-1] if is_directory and name.endswith("/") else name
    path = pathlib.PurePosixPath(canonical)
    if (not canonical or path.is_absolute() or ".." in path.parts
            or path.as_posix() != canonical or not path.parts
            or path.parts[0] in ("", ".")):
        raise ValueError(f"invalid archive member path: {name!r}")


def normalize_archive(source: pathlib.Path, output: pathlib.Path, epoch: int = DEFAULT_EPOCH) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError("raw input and normalized output must be different files")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source, mode="r:gz") as reader:
        members = reader.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive member names are not accepted")
        for member in members:
            _safe_member_name(member.name, member.isdir())
            if not (member.isdir() or member.isfile()):
                raise ValueError(f"unsupported archive member type: {member.name!r}")
        roots = {pathlib.PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError("source distribution must have one top-level directory")

        with output.open("wb") as raw_out:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, compresslevel=9, mtime=0) as gz_out:
                with tarfile.open(fileobj=gz_out, mode="w|", format=tarfile.PAX_FORMAT) as writer:
                    for member in sorted(members, key=lambda item: item.name.encode("utf-8")):
                        info = tarfile.TarInfo(member.name)
                        info.type = tarfile.DIRTYPE if member.isdir() else tarfile.REGTYPE
                        info.size = 0 if member.isdir() else member.size
                        info.mode = 0o755 if member.isdir() else 0o644
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = int(epoch)
                        info.devmajor = info.devminor = 0
                        info.pax_headers = {}
                        if member.isdir():
                            writer.addfile(info)
                        else:
                            payload = reader.extractfile(member)
                            if payload is None:
                                raise ValueError(f"archive member has no payload: {member.name!r}")
                            data = payload.read()
                            if len(data) != member.size:
                                raise ValueError(f"short archive member read: {member.name!r}")
                            writer.addfile(info, io.BytesIO(data))
    size, digest = sha256(output)
    with tarfile.open(output, mode="r:gz") as check:
        checked = check.getmembers()
        if len(checked) != len(members) or any(int(item.mtime) != int(epoch) for item in checked):
            raise RuntimeError("normalized archive metadata readback failed")
    return {"bytes": size, "sha256": digest, "members": len(members), "mtime": int(epoch)}


def build(source: pathlib.Path, output_dir: pathlib.Path, wheelhouse: pathlib.Path, timeout: int, epoch: int) -> dict:
    if importlib.metadata.version("build") != PINNED_BUILD:
        raise RuntimeError(f"build frontend must be exactly {PINNED_BUILD}")
    source = source.resolve(strict=True)
    wheelhouse = wheelhouse.resolve(strict=True)
    if not (source / "pyproject.toml").is_file():
        raise ValueError("source root must contain pyproject.toml")
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sharkbyte-sdist-raw-") as temporary:
        raw_dir = pathlib.Path(temporary)
        command = [sys.executable, "-m", "build", "--sdist", "--outdir", str(raw_dir), str(source)]
        env = os.environ.copy()
        env["PIP_NO_INDEX"] = "1"
        env["PIP_FIND_LINKS"] = str(wheelhouse)
        env["SOURCE_DATE_EPOCH"] = str(epoch)
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, env=env, check=False)
        (output_dir / "build.stdout.txt").write_text(result.stdout, encoding="utf-8")
        (output_dir / "build.stderr.txt").write_text(result.stderr, encoding="utf-8")
        (output_dir / "build.command.json").write_text(
            json.dumps({"command": command, "pep517_isolation": True, "offline": True,
                        "build_frontend": PINNED_BUILD, "exit_code": result.returncode},
                       sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        if result.returncode != 0:
            raise RuntimeError(f"PEP 517 isolated build failed with exit {result.returncode}")
        archives = sorted(raw_dir.glob("*.tar.gz"))
        if len(archives) != 1:
            raise RuntimeError(f"expected one raw source archive, found {len(archives)}")
        raw_archive = output_dir / (archives[0].name + ".un-normalized")
        shutil.copyfile(archives[0], raw_archive)
        final_archive = output_dir / archives[0].name
        normalized = normalize_archive(raw_archive, final_archive, epoch)
        raw_size, raw_sha = sha256(raw_archive)
        return {
            "archive": final_archive.name,
            "raw_archive": raw_archive.name,
            "raw_bytes": raw_size,
            "raw_sha256": raw_sha,
            "normalized": normalized,
            "build_isolation": "PEP 517 isolation enabled",
            "status": "PASS",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument("--wheelhouse", type=pathlib.Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--epoch", type=int, default=DEFAULT_EPOCH)
    args = parser.parse_args()
    if args.timeout < 1 or args.epoch < 0:
        parser.error("timeout must be positive and epoch nonnegative")
    try:
        report = build(args.source, args.output_dir, args.wheelhouse, args.timeout, args.epoch)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
