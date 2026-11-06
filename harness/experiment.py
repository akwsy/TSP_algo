"""Run a named experiment: python3 -m harness.experiment scaling [options]

Runs every algorithm on the same instances (seeds 1..N for each size), writes
per-run results tagged with the experiment name, and writes
<results-dir>/aggregates-<experiment>.json.
"""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .aggregate import aggregate
from .config import ConfigError, InstanceConfig
from .dataset import DatasetError, load_places
from .experiments import EXPERIMENTS
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .run import ROOT, discover_algorithms, run_batch

DEFAULTS = InstanceConfig(seed=0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.experiment",
                                 description="Run a named experiment and aggregate the results.")
    ap.add_argument("name", help="experiment name: " + ", ".join(EXPERIMENTS))
    ap.add_argument("--sizes", type=int, nargs="+", help="customer counts (default: the experiment's)")
    ap.add_argument("--instances", type=int, help="instances (seeds 1..N) per size")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--algorithms-dir", default=str(ROOT / "algorithms"))
    ap.add_argument("--instances-dir", default="instances")
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args(argv)

    if args.name not in EXPERIMENTS:
        print(f"error: unknown experiment {args.name!r}; known: {', '.join(EXPERIMENTS)}",
              file=sys.stderr)
        return 2
    exp = EXPERIMENTS[args.name]
    if args.sizes:
        exp = replace(exp, sizes=tuple(args.sizes))
    if args.instances is not None:
        exp = replace(exp, instances_per_size=args.instances)
    seeds = list(range(1, exp.instances_per_size + 1))
    try:
        if not seeds:
            raise ConfigError("instances per size must be at least 1")
        places = load_places(args.dataset)
        instances = [build_instance(places, InstanceConfig(seed=s, num_customers=n))
                     for n in exp.sizes for s in seeds]
        algorithms = discover_algorithms(args.algorithms_dir)
    except (ConfigError, DatasetError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not algorithms:
        print(f"error: no algorithm.json found under {args.algorithms_dir}", file=sys.stderr)
        return 2

    records = run_batch(algorithms, instances, Path(args.instances_dir), Path(args.results_dir),
                        extra={"experiment": exp.name})
    result = aggregate(records)
    result = {"experiment": exp.name, "parameters": {
        "sizes": list(exp.sizes), "instancesPerSize": exp.instances_per_size, "seeds": seeds,
        "departureMinute": DEFAULTS.departure_minute, "periodMinutes": DEFAULTS.period_minutes,
        "speedKmh": DEFAULTS.speed_kmh}, **result}
    out = Path(args.results_dir) / f"aggregates-{exp.name}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
