"""Compare local SharkByte backends against fixed, hand-derived answers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
CASES = {
    'recursion': ('fun fact(n) { if (n < 2) { return 1; } return n * fact(n - 1); } print fact(6);', '720\n', None),
    'array': ('let a = array(3); a[0] = 7; a[2] = 9; print a[0] * a[2];', '63\n', None),
    'signed_arithmetic': ('print (0 - 17) / 5; print (0 - 17) % 5;', '-3\n-2\n', None),
    'characters': ('putc 65; putc 32; putc 66; putc 10;', 'A B\n', None),
    'division_sign_matrix': (
        'print 17 / 5; print 17 % 5; print 17 / (0 - 5); print 17 % (0 - 5); '
        'print (0 - 17) / 5; print (0 - 17) % 5; '
        'print (0 - 17) / (0 - 5); print (0 - 17) % (0 - 5);',
        '3\n2\n-3\n2\n-3\n-2\n3\n-2\n', None),
    'signed_wraparound': (
        'let m = 9223372036854775807; print m + 1; print m * 2;',
        '-9223372036854775808\n-2\n', None),
    'division_overflow': (
        'let m = 9223372036854775807 + 1; print m / (0 - 1);',
        '', 'integer division overflow'),
    'array_bounds': ('let a = array(3); print a[3];', '', 'array index out of bounds'),
    'division_by_zero': ('print 7 / 0;', '', 'division by zero'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = Path(tempfile.mkdtemp(prefix='backend-suite-', dir=ROOT))
    rows = []
    for name, (source, expected, error) in CASES.items():
        path = evidence / (name + '.sb')
        path.write_bytes(source.encode('ascii'))
        for backend in ('vm', 'native_interpreter', 'direct_native'):
            row = dict(case=name, backend=backend, source_sha256=digest(path),
                       expected_stdout=expected, expected_error=error)
            try:
                result = subprocess.run(
                    [sys.executable, '-B', str(ROOT / 'sharkbyte_local.py'), backend, str(path)],
                    capture_output=True, timeout=40,
                )
                stdout = result.stdout.decode('utf-8', errors='replace')
                stderr = result.stderr.decode('utf-8', errors='replace')
                folder = next((Path(line.removeprefix('Artifacts: ')) for line in stderr.splitlines()
                               if line.startswith('Artifacts: ')), None)
                elf = folder / (backend + '.elf') if folder else None
                if backend == 'vm':
                    artifact_hash = digest(folder / 'vm.sbc') if folder and (folder / 'vm.sbc').is_file() else None
                else:
                    artifact_hash = digest(elf) if elf and elf.is_file() else None
                correct_exit = (result.returncode == 0 and all(
                    line.startswith(('Artifacts: ', 'Running '))
                    for line in stderr.splitlines()
                )) if error is None else (
                    result.returncode == (1 if backend == 'vm' else 70)
                    and stderr.rstrip().lower().endswith(error)
                )
                row.update(exit=result.returncode, stdout=stdout, stderr=stderr,
                           artifact_sha256=artifact_hash,
                           passed=stdout == expected and correct_exit and bool(artifact_hash))
            except (OSError, subprocess.TimeoutExpired) as exc:
                row.update(passed=False, infrastructure_error=str(exc))
            rows.append(row)
            print(f'{name} / {backend}: ' + ('PASS' if row['passed'] else 'FAIL'), flush=True)
    receipt = evidence / 'results.json'
    receipt.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    passed = sum(row['passed'] for row in rows)
    print(f'{passed}/{len(rows)} passed. Results: {receipt}')
    return int(passed != len(rows))


if __name__ == '__main__':
    raise SystemExit(main())
