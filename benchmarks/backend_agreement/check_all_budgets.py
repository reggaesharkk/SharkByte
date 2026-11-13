"""Check the step-limit diagnostic for each local backend."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
failed = False
for backend in ('vm', 'native_interpreter', 'direct_native'):
    try:
        result = subprocess.run(
            [sys.executable, '-B', str(root / 'sharkbyte_local.py'), backend,
             str(root / 'budget_loop.sb'), '--native-timeout', '120'],
            capture_output=True, text=True, timeout=160,
        )
        expected_exit = 1 if backend == 'vm' else 70
        passed = (result.returncode == expected_exit and not result.stdout
                  and result.stderr.rstrip().endswith('Execution step limit exceeded')
                  and 'TimeoutExpired' not in result.stderr)
        print(f'{backend}: {"PASS" if passed else "FAIL"} (exit {result.returncode})',
              flush=True)
        if not passed:
            print(result.stderr, file=sys.stderr)
        failed |= not passed
    except subprocess.TimeoutExpired:
        print(f'{backend}: FAIL (wall-clock timeout)', flush=True)
        failed = True
raise SystemExit(int(failed))
