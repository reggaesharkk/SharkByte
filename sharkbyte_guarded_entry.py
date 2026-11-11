"""Console entry point that detects another installed SharkByte on PYTHONPATH."""
import os, pathlib, sys

def main():
    own = pathlib.Path(__file__).resolve().parent / 'sharkbyte_alpha'
    for raw in os.environ.get('PYTHONPATH', '').split(os.pathsep):
        if not raw:
            continue
        try:
            other = pathlib.Path(raw).resolve() / 'sharkbyte_alpha'
            if other.is_dir() and other.resolve() != own.resolve():
                print('sharkbyte: conflicting SharkByte installation on PYTHONPATH; clear PYTHONPATH or run this environment\'s Python with -I -m sharkbyte_alpha',file=sys.stderr)
                return 2
        except OSError as exc:
            print('sharkbyte: unable to inspect PYTHONPATH: '+str(exc),file=sys.stderr)
            return 2
    from sharkbyte_alpha.cli import main as cli_main
    return cli_main()
