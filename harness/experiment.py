"""Run a named experiment: python3 -m harness.experiment scaling [options]

Runs every algorithm on the same instances (seeds 1..N for each size), writes
per-run results tagged with the experiment name, and writes
<results-dir>/aggregates-<experiment>.json.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from .aggregate import aggregate
from .config import ConfigError, InstanceConfig
from .dataset import DatasetError, load_places
from .experiments import EXPERIMENTS
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .run import ROOT, discover_algorithms, instance_hash, run_batch
from .session import run_session

DEFAULTS = InstanceConfig(seed=0)


def run_full_sessions(algorithms, instances, records, results_dir, exp, count):
    """Run each algorithm day by day on the first `count` seeds of each size and save one session
    file each (layout: harness/session.py). Day 1 reuses the first-day record. Ticket 03 will add
    reuse of saved sessions here."""
    chosen = [i for i in instances if i["seed"] <= count]
    out = results_dir / "sessions"
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    first_days = {(r["algorithmId"], r["instanceId"]): r for r in records}
    for meta in algorithms:
        for inst in chosen:
            session = run_session(meta, inst, run_id, first_day=first_days.get((meta["id"], inst["instanceId"])))
            session.update(experiment=exp.name, instanceHash=instance_hash(inst))
            name = f"{meta['id']}__{inst['instanceId']}__{run_id}.json"
            (out / name).write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
            print(f"{meta['id']} until every place is visited on {inst['instanceId']}: "
                  f"{session['outcome']}, {session['days']} days", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.experiment",
                                 description="Run a named experiment and aggregate the results.")
    ap.add_argument("name", help="experiment name: " + ", ".join(EXPERIMENTS))
    ap.add_argument("--sizes", type=int, nargs="+", help="customer counts (default: the experiment's)")
    ap.add_argument("--instances", type=int, help="instances (seeds 1..N) per size")
    ap.add_argument("--full-run-instances", type=int, default=10, metavar="N",
                    help="run the first N instances of each size until every place is visited "
                         "(default 10, 0 to skip; never more than --instances)")
    ap.add_argument("--force", action="store_true",
                    help="re-evaluate everything, ignoring saved runs")
    ap.add_argument("--rerun", nargs="+", metavar="ID", default=[],
                    help="re-evaluate only these algorithms (their saved runs are not reused)")
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

    unknown = [a for a in args.rerun if a not in {m["id"] for m in algorithms}]
    if unknown:
        print(f"error: --rerun: no such algorithm: {', '.join(unknown)}", file=sys.stderr)
        return 2
    stats = {}
    records = run_batch(algorithms, instances, Path(args.instances_dir), Path(args.results_dir),
                        extra={"experiment": exp.name}, reuse=not args.force,
                        rerun=set(args.rerun), stats=stats)
    if args.full_run_instances < 0:
        print("error: --full-run-instances must not be negative", file=sys.stderr)
        return 2
    run_full_sessions(algorithms, instances, records, Path(args.results_dir), exp,
                      min(args.full_run_instances, exp.instances_per_size))
    reused, ran = sum(stats["reused"].values()), sum(stats["ran"].values())
    print(f"Reused {reused} saved runs, ran {ran} new.")
    for meta in algorithms:
        a = meta["id"]
        print(f"  {a}: reused {stats['reused'].get(a, 0)}, ran {stats['ran'].get(a, 0)}")
    if stats["legacy"]:
        print(f"Note: {stats['legacy']} older saved runs have no fingerprint, so they were not reused.")
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
