"""Run every experiment folder in order, one after the other.

    python3 run_all_experiments.py            all experiments (can take a long time)
    python3 run_all_experiments.py --quick    a very small run of each (a few minutes in all)

Extra arguments are passed on to every experiment's run.py. Each experiment writes its own
`output/` folder; the summary at the end says where.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv):
    scripts = sorted((ROOT / "experiments").glob("*/run.py"))
    results = []
    for number, script in enumerate(scripts, start=1):
        print(f"\n=== [{number}/{len(scripts)}] {script.parent.name} ===", flush=True)
        t0 = time.perf_counter()
        code = subprocess.call([sys.executable, str(script)] + list(argv), cwd=ROOT)
        results.append((script.parent, code, time.perf_counter() - t0))
    print("\n=== Summary ===")
    for folder, code, secs in results:
        status = "ok" if code == 0 else f"FAILED (exit {code})"
        print(f"{folder.name}: {status}, {secs:.0f} s\n    output: {folder / 'output'}")
    print("\nLook at an output on the website, for example:")
    if results:
        out = results[0][0] / "output"
        print(f"  python3 site/serve.py --results {out / 'results'} --algorithms algorithms "
              f"--instances {out / 'instances'}")
    return 0 if all(code == 0 for _, code, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
