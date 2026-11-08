"""Run a named experiment: python3 -m harness.experiment scaling [options]
   Run all of them:        python3 -m harness.experiment suite
   List them:              python3 -m harness.experiment --list

An experiment (harness/experiments.py) varies one parameter over several values. Every algorithm
runs on the same instances (seeds 1..N for each value). Each run and index entry is tagged with
`experiment`, `sweepParam` and `sweepValue`, and <results-dir>/aggregates-<experiment>.json is
written (groups per algorithm and sweep value, plus the paired comparisons under `pairs`). The
suite runs every experiment and then writes <results-dir>/suite.json listing them.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path

from .aggregate import aggregate, aggregate_sessions, pairwise
from .config import ConfigError
from .dataset import DatasetError, load_places
from .experiments import EXPERIMENTS, PARAMS
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .run import ROOT, discover_algorithms, instance_hash, run_batch
from . import session as sessionlib
from .session import MAX_DAYS, run_session
from .sessionstore import find_saved_session, read_sessions_index, save_session, session_key

SUITE = "suite"
# Experiment parameter name -> key in the aggregates `parameters` block.
PARAMETER_KEYS = {"customers": "customers", "departure": "departureMinute",
                  "period": "periodMinutes", "speed": "speedKmh", "radius": "radiusKm"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def parameters_block(exp, seeds):
    """The `parameters` block of the aggregates file: the sweep, the seeds and the value of every
    parameter that is not swept (the swept one is left out; for a customers sweep `sizes` holds
    the values, as it always has)."""
    base = exp.config(seeds[0], exp.values[0])
    effective = {"customers": base.num_customers, "departure": base.departure_minute,
                 "period": base.period_minutes, "speed": base.speed_kmh, "radius": base.radius_km}
    block = {}
    if exp.param == "customers":
        block["sizes"] = list(exp.values)
    block.update(sweepParam=exp.param, values=list(exp.values),
                 instancesPerSize=exp.instances_per_size, seeds=seeds)
    for name, key in PARAMETER_KEYS.items():
        if name != exp.param:
            block[key] = effective[name]
    return block


def run_experiment(exp, algorithms, places, results_dir, instances_dir, full_run_instances,
                   reuse=True, rerun=(), max_days=MAX_DAYS, out=print):
    """Run one experiment (a possibly overridden Experiment) and write its aggregates file.
    Prints one progress line per sweep value. Returns the path written."""
    seeds = list(range(1, exp.instances_per_size + 1))
    if not seeds:
        raise ConfigError("instances per size must be at least 1")
    by_value = [(v, [build_instance(places, exp.config(s, v)) for s in seeds]) for v in exp.values]
    records, instances = [], []
    stats = {"reused": {}, "ran": {}, "legacy": 0}
    started = time.perf_counter()
    for number, (value, batch) in enumerate(by_value, start=1):
        t0 = time.perf_counter()
        part = {}
        mine = run_batch(
            algorithms, batch, instances_dir, results_dir, extra={"experiment": exp.name},
            reuse=reuse, rerun=set(rerun), stats=part, verbose=False,
            tag=lambda inst, v=value: {"sweepParam": exp.param, "sweepValue": v})
        records += mine
        instances += batch
        for key in ("reused", "ran"):
            for a, n in part[key].items():
                stats[key][a] = stats[key].get(a, 0) + n
        stats["legacy"] += part["legacy"]
        out(f"[{exp.name}] {exp.param}={value:g} ({number}/{len(by_value)}): {len(mine)} runs "
            f"({len(algorithms)} algorithms x {len(batch)} instances), "
            f"{sum(1 for r in mine if not r['valid'])} failed, "
            f"{sum(1 for r in mine if r.get('killed'))} timed out, "
            f"{time.perf_counter() - t0:.1f} s")
    sessions, full = [], None
    if exp.param == "customers" and full_run_instances > 0:
        full = {}
        sessions = run_full_sessions(algorithms, instances, records, results_dir, exp,
                                     min(full_run_instances, exp.instances_per_size),
                                     reuse=reuse, rerun=set(rerun), stats=full, max_days=max_days)
    reused, ran = sum(stats["reused"].values()), sum(stats["ran"].values())
    if reuse:
        out(f"Reusing {reused} saved runs, running {ran} new.")
    out(f"[{exp.name}] reused {reused} saved runs, ran {ran} new, "
        f"{time.perf_counter() - started:.1f} s in all.")
    for meta in algorithms:
        a = meta["id"]
        out(f"  {a}: reused {stats['reused'].get(a, 0)}, ran {stats['ran'].get(a, 0)}")
    if full is not None:
        out(f"Full run: reused {sum(full['reused'].values())} saved sessions, "
            f"ran {sum(full['ran'].values())} new.")
        for meta in algorithms:
            a = meta["id"]
            out(f"  {a}: reused {full['reused'].get(a, 0)}, ran {full['ran'].get(a, 0)}")
    if stats["legacy"]:
        out(f"Note: {stats['legacy']} older saved runs have no fingerprint, so they were not reused.")
    result = aggregate(records)
    result = {"experiment": exp.name, "parameters": parameters_block(exp, seeds), **result,
              "pairs": pairwise(records)}
    if sessions:  # full-run block: see aggregate_sessions (hours, km, ms; own `ranking`/`overall`)
        result["full"] = aggregate_sessions(sessions)
    path = Path(results_dir) / f"aggregates-{exp.name}.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    out(f"wrote {path}")
    return path


def write_suite(results_dir, entries):
    path = Path(results_dir) / "suite.json"
    path.write_text(json.dumps({"generatedAt": utc_now(), "experiments": entries}, indent=2) + "\n",
                    encoding="utf-8")
    return path


def parse_fixed(items):
    fixed = {}
    for item in items or []:
        name, _, raw = item.partition("=")
        if name not in PARAMS or not raw:
            raise ConfigError(f"--fixed expects NAME=VALUE with NAME one of {', '.join(PARAMS)}: {item!r}")
        try:
            fixed[name] = float(raw) if name in ("speed", "radius") else int(raw)
        except ValueError:
            raise ConfigError(f"--fixed {item!r}: not a number") from None
    return fixed


def main(argv=None, experiments=None):
    experiments = EXPERIMENTS if experiments is None else experiments
    ap = argparse.ArgumentParser(prog="python3 -m harness.experiment",
                                 description="Run a named experiment (or the whole suite) and aggregate the results.")
    ap.add_argument("name", nargs="?",
                    help="experiment name: " + ", ".join(experiments) + f", or {SUITE} to run them all")
    ap.add_argument("--list", action="store_true", help="print the experiments and exit")
    ap.add_argument("--values", type=float, nargs="+", help="sweep values (default: the experiment's)")
    ap.add_argument("--sizes", type=int, nargs="+", help="customer counts: same as --values, for scaling and stress")
    ap.add_argument("--instances", type=int, help="instances (seeds 1..N) per sweep value")
    ap.add_argument("--fixed", nargs="+", metavar="NAME=VALUE",
                    help="override fixed parameters, e.g. customers=20")
    ap.add_argument("--full-run-instances", type=int, default=None, metavar="N",
                    help="run the first N instances of each size until every place is visited "
                         "(customers experiments only; default: the experiment's, 10 for scaling "
                         "and 0 otherwise; never more than --instances)")
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

    if args.list:
        for e in experiments.values():
            fixed = ", ".join(f"{k}={v}" for k, v in e.fixed.items()) or "defaults"
            print(f"{e.name}: {e.description}\n    varies {e.param} over "
                  f"{', '.join(f'{v:g}' for v in e.values)}; {e.instances_per_size} instances "
                  f"each; fixed: {fixed}")
        return 0
    if args.name is None:
        print(f"error: give an experiment name ({', '.join(experiments)}, {SUITE}) or --list",
              file=sys.stderr)
        return 2
    if args.max_days < 1:
        print("error: --max-days must be a positive whole number", file=sys.stderr)
        return 2
    if args.full_run_instances is not None and args.full_run_instances < 0:
        print("error: --full-run-instances must not be negative", file=sys.stderr)
        return 2
    suite = args.name == SUITE
    if not suite and args.name not in experiments:
        print(f"error: unknown experiment {args.name!r}; known: {', '.join(experiments)}, {SUITE}",
              file=sys.stderr)
        return 2
    if suite and (args.values or args.sizes or args.fixed):
        print("error: --values, --sizes and --fixed apply to one experiment, not the suite",
              file=sys.stderr)
        return 2
    chosen = list(experiments.values()) if suite else [experiments[args.name]]
    try:
        fixed = parse_fixed(args.fixed)
        overridden = []
        for exp in chosen:
            over = {}
            raw = args.values if args.values is not None else args.sizes
            if raw:
                whole = exp.param in ("customers", "period", "departure")
                over["values"] = tuple(int(v) if whole else v for v in raw)
            if args.instances is not None:
                over["instances_per_size"] = args.instances
            if fixed:
                over["fixed"] = {**exp.fixed, **fixed}
            overridden.append(replace(exp, **over) if over else exp)
        places = load_places(args.dataset)
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

    results_dir = Path(args.results_dir)
    entries = []
    started = time.perf_counter()
    for exp in overridden:
        full = exp.full_run_instances if args.full_run_instances is None else args.full_run_instances
        try:
            path = run_experiment(exp, algorithms, places, results_dir, Path(args.instances_dir),
                                  full, reuse=not args.force, rerun=args.rerun,
                                  max_days=args.max_days)
        except (ConfigError, ValueError) as e:
            print(f"error: {exp.name}: {e}", file=sys.stderr)
            return 2
        entries.append({"name": exp.name, "description": exp.description, "param": exp.param,
                        "values": list(exp.values), "instancesPerSize": exp.instances_per_size,
                        "algorithms": sorted(m["id"] for m in algorithms),
                        "aggregates": path.name, "timestamp": utc_now()})
    if suite:
        print(f"wrote {write_suite(results_dir, entries)} "
              f"(suite took {time.perf_counter() - started:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
