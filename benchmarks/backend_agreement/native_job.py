"""Validate and bind source submitted to a future contained native worker."""
from dataclasses import dataclass
from hashlib import sha256

BACKENDS = frozenset({"native_interpreter", "direct_native"})
MAX_SOURCE_BYTES = 65536


@dataclass(frozen=True)
class NativeJob:
    backend: str
    source: bytes
    source_sha256: str

    @classmethod
    def from_request(cls, request):
        if type(request) is not dict or request.keys() != {"backend", "source"}:
            raise ValueError("Expected backend and source")
        backend, source = request["backend"], request["source"]
        if type(backend) is not str or backend not in BACKENDS:
            raise ValueError("Unsupported native backend")
        if type(source) is not str or len(source) > MAX_SOURCE_BYTES:
            raise ValueError("Invalid source or source exceeds byte limit")
        try:
            data = source.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("Source must be valid UTF-8") from error
        if len(data) > MAX_SOURCE_BYTES or not data or b"\x00" in data:
            raise ValueError("Source must be nonempty, bounded and free of NUL bytes")
        return cls(backend, data, sha256(data).hexdigest())
