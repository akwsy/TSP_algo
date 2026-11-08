"""Run experiment stress (stress-large-problems).

    python3 experiments/06-stress-large-problems/run.py            the full experiment
    python3 experiments/06-stress-large-problems/run.py --quick    a very small run (values 100 and 150, 3 examples)
    python3 experiments/06-stress-large-problems/run.py --help     (extra arguments are passed to the harness)

Works from any directory. Output goes into the `output/` folder next to this file:
output/results (one file per run, index.json, aggregates-stress.json) and output/instances.
"""
import subprocess
import sys
from pathlib import Path

EXPERIMENT = "stress"
FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]  # the G4T1 folder
BASE = ["-m", "harness.experiment", EXPERIMENT,
        "--results-dir", str(FOLDER / "output" / "results"),
        "--instances-dir", str(FOLDER / "output" / "instances")]
QUICK = ['--values', '100', '150', '--instances', '3']


def main(argv):
    extra = list(argv)
    quick = "--quick" in extra
    extra = [a for a in extra if a != "--quick"]
    command = [sys.executable] + BASE + (QUICK if quick else []) + extra
    print("Running:", "python3 " + " ".join(command[1:]), flush=True)
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
