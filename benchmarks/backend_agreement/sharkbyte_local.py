"""Run local, trusted SharkByte programs from the Ubuntu terminal."""
import argparse
import os
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

from native_compile import compile_job

ROOT = Path(os.environ.get('SHARKBYTE_NATIVE_ROOT', '/mnt/d/SharkByteControl/dev_8099B_audit_20261110/dependencies/8093')).resolve()
sys.path.insert(0, str(ROOT / 'backend'))
from direct_aarch64 import compile_source

spec = importlib.util.spec_from_file_location('reference_vm', ROOT / 'reference/vm/sharkbyte_v05.py')
vm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vm
spec.loader.exec_module(vm)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('backend', choices=('vm', 'direct_native', 'native_interpreter', 'all'))
parser.add_argument('source', type=Path)
parser.add_argument('--native-timeout', type=int, default=5,
                    help='Native wall-clock timeout in seconds (1 to 300)')
args = parser.parse_args()
if not 1 <= args.native_timeout <= 300:
    parser.error('--native-timeout must be between 1 and 300 seconds')
with args.source.open('rb') as source_file:
    raw = source_file.read(65537)
if not raw or len(raw) > 65536 or b'\x00' in raw:
    parser.error('Expected a nonempty UTF-8 source file of at most 65536 bytes')
program = raw.decode('utf-8')
backends = ('vm', 'direct_native', 'native_interpreter') if args.backend == 'all' else (args.backend,)
out = Path(tempfile.mkdtemp(prefix='local-run-', dir=Path(__file__).resolve().parent))
print(f"Artifacts: {out}", file=sys.stderr)
for backend in backends:
    if backend == 'vm':
        bytecode = vm.encode(*vm.compile_source(program))
        (out / 'vm.sbc').write_bytes(bytecode)
        sys.stdout.write(vm.run_vm(bytecode, max_steps=50_000_000))
        continue
    artifact = compile_job({'backend': backend, 'source': program},
                           direct_compile=compile_source,
                           bytecode_compile=vm.compile_source, bytecode_encode=vm.encode)
    if backend == 'direct_native':
        source = out / 'direct.S'
        source.write_bytes(artifact.data)
        runtime = [ROOT / 'runtime/print_i64.S', ROOT / 'runtime/runtime_v06.c']
    else:
        source = out / 'program.c'
        literals = ','.join(map(str, artifact.data))
        source.write_text(f'const unsigned char sb_program[]={{ {literals} }};\n'
                          f'const unsigned long sb_program_len={len(artifact.data)}UL;\n')
        runtime = [ROOT / 'reference/native/runtime_v05.c']
    elf = out / (backend + '.elf')
    subprocess.run(['/usr/bin/clang', '--target=aarch64-linux-gnu', '-O2',
                    '-fno-builtin', '-fuse-ld=lld', '-nostdlib', '-static',
                    '-Wl,-e,_start', '-Wl,--build-id=none', source, *runtime, '-o', elf],
                   check=True, timeout=20)
    with elf.open('rb') as stream:
        header = stream.read(20)
    if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\xb7\x00':
        raise RuntimeError(f'Unexpected ELF header: {elf}')
    print(f'Running {backend}', file=sys.stderr, flush=True)
    result = subprocess.run([str(elf)], cwd=out, timeout=args.native_timeout, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
