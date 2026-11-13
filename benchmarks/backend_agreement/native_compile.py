"""Compile validated native jobs into artifacts without executing them."""
from dataclasses import dataclass
from hashlib import sha256

from native_job import NativeJob


@dataclass(frozen=True)
class NativeArtifact:
    backend: str
    source_sha256: str
    format: str
    data: bytes
    artifact_sha256: str


def compile_job(request, *, direct_compile, bytecode_compile, bytecode_encode):
    job = NativeJob.from_request(request)
    source = job.source.decode("utf-8")
    if job.backend == "direct_native":
        _, assembly = direct_compile(source)
        data = assembly.encode("utf-8")
        artifact_format = "aarch64-assembly"
    else:
        data = bytes(bytecode_encode(*bytecode_compile(source)))
        artifact_format = "sharkbyte-bytecode"
    return NativeArtifact(job.backend, job.source_sha256, artifact_format,
                          data, sha256(data).hexdigest())
