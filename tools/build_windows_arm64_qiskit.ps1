param(
    [Parameter(Mandatory)] [string] $Output,
    [Parameter(Mandatory)] [string] $RustBin,
    [Parameter(Mandatory)] [string] $MsvcRoot,
    [string] $SdkRoot = 'C:\Program Files (x86)\Windows Kits\10',
    [string] $SdkVersion = '10.0.22621.0',
    [string] $Python = 'python'
)
$ErrorActionPreference = 'Stop'
$env:SHARKBYTE_NATIVE_WHEEL_OUTPUT = [System.IO.Path]::GetFullPath($Output)
$Output = $env:SHARKBYTE_NATIVE_WHEEL_OUTPUT
$env:PATH = "$RustBin;$MsvcRoot\bin\Hostarm64\arm64;$SdkRoot\bin\$SdkVersion\arm64;$env:PATH"
$env:LIB = "$MsvcRoot\lib\arm64;$SdkRoot\Lib\$SdkVersion\ucrt\arm64;$SdkRoot\Lib\$SdkVersion\um\arm64"
$env:INCLUDE = "$MsvcRoot\include;$SdkRoot\Include\$SdkVersion\ucrt;$SdkRoot\Include\$SdkVersion\shared;$SdkRoot\Include\$SdkVersion\um"
$env:CARGO_HOME = Join-Path $Output 'cargo-home'
$env:CARGO_BUILD_JOBS = '3'
@"
import hashlib, json, os, platform, sys, tarfile, urllib.request
from pathlib import Path

if sys.platform != "win32" or platform.machine() != "ARM64" or sys.version_info[:2] != (3, 12):
    raise SystemExit("Use native Windows ARM64 CPython 3.12.")
root = Path(os.environ["SHARKBYTE_NATIVE_WHEEL_OUTPUT"])
root.mkdir(exist_ok=False)
pins = [
    ("rustworkx", "0.18.1", "30affe6ee52a6257a01152418f9c1686ca114e7ab4a3bf87bb87fe35b7350f3e"),
    ("qiskit", "2.6.2", "b85b5f7b56700b864cc06dbfb33f01453a42024cf5ab954a0e0a275127ebd255"),
]
for name, ver, expected in pins:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{ver}/json") as response:
        meta = json.load(response)
    source = next(item for item in meta["urls"] if item["packagetype"] == "sdist")
    with urllib.request.urlopen(source["url"]) as response:
        raw = response.read()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Unexpected source bytes for {name}")
    archive = root / source["filename"]
    archive.write_bytes(raw)
    with tarfile.open(archive) as tar:
        tar.extractall(root, filter="data")
"@ | & $Python -
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& $Python -m venv "$Output\.venv"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$venvPython = "$Output\.venv\Scripts\python.exe"
foreach ($project in @('rustworkx-0.18.1','qiskit-2.6.2')) {
    Push-Location -LiteralPath "$Output\$project"
    try {
        Copy-Item -LiteralPath Cargo.lock -Destination Cargo.upstream.lock
        if ($project -like 'rustworkx-*') {
            cargo metadata --format-version 1 > "$Output\$project.metadata.json"
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
@"
from pathlib import Path
import tomllib
def packages(path):
    return {(p["name"], p["version"], p.get("source"), p.get("checksum"))
            for p in tomllib.loads(Path(path).read_text())["package"]}
if packages("Cargo.lock") - packages("Cargo.upstream.lock"):
    raise ValueError("rustworkx lockfile changed package identities")
"@ | & $venvPython -
            if ($LASTEXITCODE) { exit $LASTEXITCODE }
        }
        cargo metadata --format-version 1 --locked > "$Output\$project.metadata.json"
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
        & $venvPython -m pip wheel --no-deps --wheel-dir "$Output\wheelhouse" .
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
    }
}
