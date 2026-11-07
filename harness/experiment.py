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

from .aggregate import aggregate, aggregate_sessions
from .config import ConfigError, InstanceConfig
from .dataset import DatasetError, load_places
from .experiments import EXPERIMENTS
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .run import ROOT, discover_algorithms, instance_hash, run_batch
from . import session as sessionlib
from .session import MAX_DAYS, run_session
from .sessionstore import find_saved_session, read_sessions_index, save_session, session_key

DEFAULTS = InstanceConfig(seed=0)


def run_full_sessions(algorithms, instances, records, results_dir, exp, count, reuse=True, rerun=(), stats=None, max_days=None):
    """Run each algorithm day by day on the first `count` seeds of each size and save one session
    file each (layout and index: harness/session.py, harness/sessionstore.py). Day 1 reuses the
    first-day record. A session already saved for the same algorithm code, instance and experiment
    is reused, not run again (unless reuse is False or the algorithm is in `rerun`).
    Returns the list of sessions (reused and newly run); `stats`, if given, is filled with
    {"reused": {id: n}, "ran": {id: n}}. `max_days` is the day cap (default MAX_DAYS, 30)."""
    chosen = [i for i in instances if i["seed"] <= count]
    (results_dir / "sessions").mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    first_days = {(r["algorithmId"], r["instanceId"]): r for r in records}
    entries = read_sessions_index(results_dir)
    stats = stats if stats is not None else {}
    stats.update(reused={}, ran={})
    sessions = []
    for meta in algorithms:
        for inst in chosen:
            key = session_key({
                "algorithmId": meta["id"], "fingerprint": meta["_fingerprint"],
                "instanceHash": instance_hash(inst), "experiment": exp.name,
                "formatVersion": sessionlib.SESSION_FORMAT_VERSION, "maxDays": max_days or MAX_DAYS})
            saved = (find_saved_session(entries, results_dir, key)
                     if reuse and meta["id"] not in rerun else None)
            if saved is not None:
                stats["reused"][meta["id"]] = stats["reused"].get(meta["id"], 0) + 1
                sessions.append(saved)
                continue
            stats["ran"][meta["id"]] = stats["ran"].get(meta["id"], 0) + 1
            session = run_session(meta, inst, run_id, first_day=first_days.get((meta["id"], inst["instanceId"])),
                                   max_days=max_days)
            session.update(experiment=exp.name, instanceHash=key[2])
            entries = save_session(results_dir, entries, session)
            print(f"{meta['id']} until every place is visited on {inst['instanceId']}: "
                  f"{session['outcome']}, {session['days']} days", flush=True)
            sessions.append(session)
    return sessions


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.experiment",
                                 description="Run a named experiment and aggregate the results.")
    ap.add_argument("name", help="experiment name: " + ", ".join(EXPERIMENTS))
    ap.add_argument("--sizes", type=int, nargs="+", help="customer counts (default: the experiment's)")
    ap.add_argument("--instances", type=int, help="instances (seeds 1..N) per size")
    ap.add_argument("--full-run-instances", type=int, default=10, metavar="N",
                    help="run the first N instances of each size until every place is visited "
                         "(default 10, 0 to skip; never more than --instances)")
    ap.add_argument("--max-days", type=int, default=MAX_DAYS, metavar="N",
                    help=f"advanced: stop a session after day N if places are still unvisited "
                         f"(default {MAX_DAYS}); a different N is re-evaluated, not reused")
    ap.add_argument("--force", action="store_true",
                    help="re-evaluate everything, ignoring saved runs")
    ap.add_argument("--rerun", nargs="+", metavar="ID", default=[],
                    help="re-evaluate only these algorithms (their saved runs are not reused)")
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--algorithms-dir", default=str(ROOT / "algorithms"))
    ap.add_argument("--instances-dir", default="instances")
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args(argv)

    if args.max_days < 1:
        print("error: --max-days must be a positive whole number", file=sys.stderr)
        return 2
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
    full = {}
    sessions = run_full_sessions(algorithms, instances, records, Path(args.results_dir), exp,
                                 min(args.full_run_instances, exp.instances_per_size),
                                 reuse=not args.force, rerun=set(args.rerun), stats=full,
                                 max_days=args.max_days)
    reused, ran = sum(stats["reused"].values()), sum(stats["ran"].values())
    print(f"Reused {reused} saved runs, ran {ran} new.")
    for meta in algorithms:
        a = meta["id"]
        print(f"  {a}: reused {stats['reused'].get(a, 0)}, ran {stats['ran'].get(a, 0)}")
    if args.full_run_instances > 0:
        print(f"Full run: reused {sum(full['reused'].values())} saved sessions, "
              f"ran {sum(full['ran'].values())} new.")
        for meta in algorithms:
            a = meta["id"]
            print(f"  {a}: reused {full['reused'].get(a, 0)}, ran {full['ran'].get(a, 0)}")
    if stats["legacy"]:
        print(f"Note: {stats['legacy']} older saved runs have no fingerprint, so they were not reused.")
    result = aggregate(records)
    result = {"experiment": exp.name, "parameters": {
        "sizes": list(exp.sizes), "instancesPerSize": exp.instances_per_size, "seeds": seeds,
        "departureMinute": DEFAULTS.departure_minute, "periodMinutes": DEFAULTS.period_minutes,
        "speedKmh": DEFAULTS.speed_kmh}, **result}
    if sessions:  # full-run block: see aggregate_sessions (hours, km, ms; own `ranking`/`overall`)
        result["full"] = aggregate_sessions(sessions)
    out = Path(args.results_dir) / f"aggregates-{exp.name}.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
