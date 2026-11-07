"""Check that greedy-insertion-cached gives exactly the same routes as this original version.

Run from the repository root:

    python3 algorithms/greedy-insertion/compare.py                     # sizes 5..100, 30 seeds
    python3 algorithms/greedy-insertion/compare.py --sizes 5 10 --seeds 5

For every instance it runs both solvers in this process (so Python start-up time does not
hide the difference), validates both routes with the harness's validator, and reports any
difference in the route. Per size it prints the mean number of tries (stats.iterations),
the original's mean replayed legs (its real checking cost; the cached version does O(1) per
try), and the mean solve time of each version in milliseconds.
"""
import argparse
import json
import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness.config import InstanceConfig  # noqa: E402
from harness.dataset import load_places  # noqa: E402
from harness.instance import build_instance  # noqa: E402
from harness.validator import validate_route  # noqa: E402

VERSIONS = {
    "original": ROOT / "algorithms" / "greedy-insertion",
    "cached": ROOT / "algorithms" / "greedy-insertion-cached",
}


def load_solver(name, folder):
    spec = importlib.util.spec_from_file_location(f"solve_{name}", folder / "solve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.solve


SOLVERS = {name: load_solver(name, folder) for name, folder in VERSIONS.items()}


def run(name, instance):
    started = time.perf_counter()
    out = SOLVERS[name](json.loads(json.dumps(instance)))
    return out, (time.perf_counter() - started) * 1000


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", type=int, nargs="+", default=[5, 10, 15, 20, 30, 50, 100])
    parser.add_argument("--seeds", type=int, default=30, help="seeds 1..N per size")
    args = parser.parse_args()

    places = load_places(ROOT / "data" / "MY.txt")
    mismatches = invalid = 0
    print(f"{'size':>5} {'same':>6} {'visits':>7} {'tries orig':>11} {'tries cached':>13} "
          f"{'legs orig':>11} {'ms orig':>9} {'ms cached':>10} {'speed-up':>9}")
    for size in args.sizes:
        same = visits = 0
        work = {"original": 0, "cached": 0}
        legs = 0
        ms = {"original": 0.0, "cached": 0.0}
        for seed in range(1, args.seeds + 1):
            inst = build_instance(places, InstanceConfig(seed=seed, num_customers=size))
            routes = {}
            for name in VERSIONS:
                out, elapsed = run(name, inst)
                routes[name] = out["route"]
                work[name] += out["stats"]["iterations"]
                legs += out["stats"].get("legsReplayed", 0)
                ms[name] += elapsed
                if not validate_route(inst, out["route"])["valid"]:
                    invalid += 1
                    print(f"  INVALID: {name} on n{size}-seed{seed}")
            if routes["original"] == routes["cached"]:
                same += 1
            else:
                mismatches += 1
                print(f"  DIFFERENT on n{size}-seed{seed}: {routes}")
            visits += len(routes["cached"]) - 2
        k = args.seeds
        print(f"{size:>5} {same:>3}/{k:<2} {visits / k:>7.2f} {work['original'] / k:>11.0f} "
              f"{work['cached'] / k:>13.0f} {legs / k:>11.0f} {ms['original'] / k:>9.2f} "
              f"{ms['cached'] / k:>10.2f} {ms['original'] / max(ms['cached'], 1e-9):>8.1f}x")
    print("all routes identical and valid" if not (mismatches or invalid)
          else f"{mismatches} different, {invalid} invalid")
    return 1 if mismatches or invalid else 0


if __name__ == "__main__":
    sys.exit(main())
