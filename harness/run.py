"""Runner: python3 -m harness.run --seeds 1 2 3 [options]

Runs every algorithm found in algorithms/*/algorithm.json on the same generated
instances, validates each answer, and writes one result JSON per run plus
results/index.json.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import (ConfigError, DEFAULT_DEPARTURE, DEFAULT_PERIOD, DEFAULT_SPEED,
                     InstanceConfig)
from .dataset import DatasetError, load_places
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .validator import failure_result, validate_route

ROOT = Path(__file__).resolve().parent.parent
# Why a run produced no scorable route, recorded as `failureKind` next to the plain-text
# `failureReason` (None on a valid run). Consumers (harness/session.py) rely on the kind, not on
# the wording of the reason.
FAILURE_KINDS = ("invalid_route", "crashed", "unreadable_output", "timed_out", "could_not_start")
RESULT_FIELDS = ("valid", "failureReason", "visited", "skipped", "distanceKm", "travelMinutes",
                 "waitMinutes", "totalMinutes", "returnMinute", "schedule")


def _metadata_problem(meta):
    if not isinstance(meta, dict):
        return "must be a JSON object"
    if not isinstance(meta.get("id"), str) or not meta["id"]:
        return "'id' must be a non-empty string"
    command = meta.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        return "'command' must be a non-empty list of strings"
    limit = meta.get("timeLimitSeconds")
    if "timeLimitSeconds" in meta and (isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= 0):
        return "'timeLimitSeconds' must be a positive number"
    return None


def discover_algorithms(folder):
    """Return metadata dicts (with a private '_dir') for each algorithms/*/algorithm.json."""
    found = []
    for meta_path in sorted(Path(folder).glob("*/algorithm.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise ConfigError(f"{meta_path}: not valid JSON ({e})")
        problem = _metadata_problem(meta)
        if problem:
            raise ConfigError(f"{meta_path}: {problem}")
        meta["_dir"] = meta_path.parent
        meta["_commit"] = git_commit(meta_path.parent)  # once per algorithm, not per run
        found.append(meta)
    return found


def _git(folder, *args):
    try:
        out = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def git_commit(folder):
    """Hash of the last commit touching the algorithm folder, or None. Uncommitted changes
    (modified, staged or untracked files in the folder) append "+dirty" so results from
    unrecorded code are never grouped with the clean commit."""
    commit = _git(folder, "log", "-1", "--format=%H", "--", ".") or None
    if commit and _git(folder, "status", "--porcelain", "--", "."):
        commit += "+dirty"
    return commit


STATUSES = ("OPTIMAL", "HEURISTIC", "TIME_LIMIT")


def _text(data):
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else (data or "")


def parse_output(stdout):
    """Return (output dict, None) or (None, plain reason) for an algorithm's stdout."""
    try:
        output = json.loads(stdout)
    except ValueError:
        return None, "output is not valid JSON"
    if not isinstance(output, dict):
        return None, "output is not a JSON object"
    status = output.get("status")
    if not isinstance(status, str):
        return None, "status must be a string"
    if status not in STATUSES:
        return None, f"unknown status {status!r}"
    if "stats" in output and output["stats"] is not None and not isinstance(output["stats"], dict):
        return None, "stats must be an object"
    return output, None


def execute(meta, instance):
    """Run the algorithm once; return (output dict or None, runtimeMs, error or None, stderr,
    timedOut, error kind or None). The kind is one of FAILURE_KINDS and is set exactly when
    there is an error."""
    limit = meta.get("timeLimitSeconds", 10)
    start = time.perf_counter()
    try:
        proc = subprocess.run(meta["command"], cwd=meta["_dir"], input=json.dumps({**instance, "timeLimitSeconds": limit}).encode("utf-8"),
                              capture_output=True, timeout=limit)
    except OSError as exc:
        runtime_ms = (time.perf_counter() - start) * 1000
        return None, runtime_ms, f"could not start the command: {exc.strerror or exc}", "", False, "could_not_start"
    except subprocess.TimeoutExpired as exc:
        runtime_ms = (time.perf_counter() - start) * 1000
        error = f"exceeded the time limit of {limit} s and was killed"
        output, _ = parse_output(_text(exc.stdout)) if _text(exc.stdout).strip() else (None, None)
        if output is not None:
            output["status"] = "TIME_LIMIT"
        return output, runtime_ms, error, _text(exc.stderr), True, "timed_out"
    runtime_ms = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        return None, runtime_ms, f"exited with code {proc.returncode}", _text(proc.stderr), False, "crashed"
    output, error = parse_output(_text(proc.stdout))
    return output, runtime_ms, error, _text(proc.stderr), False, ("unreadable_output" if error else None)


def make_record(meta, instance, run_id):
    output, runtime_ms, error, stderr, timed_out, error_kind = execute(meta, instance)
    output = output or {}
    route = output.get("route")
    status = "TIME_LIMIT" if timed_out else output.get("status")
    if error and not (timed_out and route is not None):
        checked = failure_result(error)
        kind = error_kind
    else:
        checked = validate_route(instance, route)
        # A killed run with a bad route still counts as a timeout (as it always has).
        kind = None if checked["valid"] else ("timed_out" if timed_out else "invalid_route")
    record = {
        "algorithmId": meta["id"],
        "commit": meta["_commit"],
        "instanceId": instance["instanceId"],
        "seed": instance.get("seed"),
        "numCustomers": len(instance["locations"]) - 1,
        "runId": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "killed": timed_out,
        "route": route,
        "runtimeMs": runtime_ms,
        "stats": output.get("stats"),
        "stderr": stderr,
    }
    record.update({k: checked[k] for k in RESULT_FIELDS})
    record["failureKind"] = kind
    return record


def write_index(path, index):
    """Write the index atomically (temp file in the same folder, then rename)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


IGNORED_NAMES = {"__pycache__", ".DS_Store", ".git"}


def algorithm_fingerprint(folder):
    """Content hash of every file in the algorithm folder (relative path + bytes, so renames and
    algorithm.json edits count too). Bytecode caches and OS metadata are ignored."""
    folder = Path(folder)
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()
                       and not IGNORED_NAMES & set(p.relative_to(folder).parts) and p.suffix != ".pyc"):
        digest.update(path.relative_to(folder).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def instance_hash(instance):
    return hashlib.sha256(json.dumps(instance, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _find_saved(index, results_dir, meta, fingerprint, ihash, extra):
    """Latest saved record for this exact algorithm code, instance and tag, or None."""
    for entry in reversed(index["runs"]):
        if (entry.get("fingerprint") == fingerprint and entry.get("instanceHash") == ihash
                and entry["algorithmId"] == meta["id"]
                and all(entry.get(k) == v for k, v in (extra or {}).items())):
            try:
                return json.loads((results_dir / entry["file"]).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return None


def run_batch(algorithms, instances, instances_dir, results_dir, extra=None, reuse=False,
              rerun=(), stats=None):
    """Run every algorithm on every instance; write instances, one result file per run and
    results/index.json. `extra` (e.g. {"experiment": "scaling"}) is added to each record and
    index entry. Returns the list of records.

    With reuse=True a pair already saved with the same algorithm fingerprint, instance hash and
    tag is not run again: its stored record is returned and nothing is appended to the index.
    Algorithms whose id is in `rerun` are always re-run. `stats`, if given, is filled with
    {"reused": {id: n}, "ran": {id: n}, "legacy": n}."""
    instances_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    for inst in instances:
        (instances_dir / f"{inst['instanceId']}.json").write_text(
            json.dumps(inst, indent=2) + "\n", encoding="utf-8")

    index_path = results_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"runs": []}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    records = []
    stats = stats if stats is not None else {}
    stats.update(reused={}, ran={}, legacy=0)
    hashes = {inst["instanceId"]: instance_hash(inst) for inst in instances}
    if reuse:
        stats["legacy"] = sum(1 for e in index["runs"] if "fingerprint" not in e
                              and any(e["algorithmId"] == m["id"] for m in algorithms))
    plan = []
    for meta in algorithms:
        meta["_fingerprint"] = algorithm_fingerprint(meta["_dir"])
        for inst in instances:
            ihash = hashes[inst["instanceId"]]
            saved = (_find_saved(index, results_dir, meta, meta["_fingerprint"], ihash, extra)
                     if reuse and meta["id"] not in rerun else None)
            plan.append((meta, inst, ihash, saved))
    if reuse:
        n_saved = sum(1 for p in plan if p[3] is not None)
        print(f"Reusing {n_saved} saved runs, running {len(plan) - n_saved} new.", flush=True)
    for meta, inst, ihash, saved in plan:
        if saved is not None:
            records.append(saved)
            stats["reused"][meta["id"]] = stats["reused"].get(meta["id"], 0) + 1
            continue
        stats["ran"][meta["id"]] = stats["ran"].get(meta["id"], 0) + 1
        record = make_record(meta, inst, run_id)
        record.update(fingerprint=meta["_fingerprint"], instanceHash=ihash)
        record.update(extra or {})
        records.append(record)
        name = f"{record['algorithmId']}__{record['instanceId']}__{run_id}.json"
        (results_dir / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        # A forced re-run of identical code supersedes its older entry (the file stays on disk);
        # entries for other code versions are kept: they are the History page's before/after.
        index["runs"] = [e for e in index["runs"] if not (
            e.get("fingerprint") == meta["_fingerprint"] and e.get("instanceHash") == ihash
            and e["algorithmId"] == meta["id"] and all(e.get(k) == v for k, v in (extra or {}).items()))]
        index["runs"].append({
            "file": name, "runId": run_id, "algorithmId": record["algorithmId"],
            "commit": record["commit"], "instanceId": record["instanceId"],
            "numCustomers": record["numCustomers"], "seed": record["seed"],
            "timestamp": record["timestamp"], "status": record["status"], "killed": record["killed"],
            "valid": record["valid"], "visited": record["visited"],
            "distanceKm": record["distanceKm"], "runtimeMs": record["runtimeMs"],
            "failureReason": record["failureReason"], "fingerprint": record["fingerprint"],
            "instanceHash": ihash, **(extra or {})})
        write_index(index_path, index)  # after every run, so an interrupted batch stays consistent
        print(f"{record['algorithmId']} on {record['instanceId']}: "
              f"{'valid, visited ' + str(record['visited']) if record['valid'] else 'FAILED: ' + str(record['failureReason'])}",
              flush=True)
    write_index(index_path, index)
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.run",
                                 description="Run all algorithms on the same generated instances.")
    ap.add_argument("--seeds", type=int, nargs="+", required=True, help="one instance per seed")
    ap.add_argument("--customers", type=int, default=10)
    ap.add_argument("--departure", type=int, default=DEFAULT_DEPARTURE)
    ap.add_argument("--period", type=int, default=DEFAULT_PERIOD)
    ap.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--algorithms-dir", default=str(ROOT / "algorithms"))
    ap.add_argument("--instances-dir", default="instances")
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args(argv)

    try:
        places = load_places(args.dataset)
        instances = [build_instance(places, InstanceConfig(
            seed=s, num_customers=args.customers, departure_minute=args.departure,
            period_minutes=args.period, speed_kmh=args.speed)) for s in args.seeds]
        algorithms = discover_algorithms(args.algorithms_dir)
    except (ConfigError, DatasetError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not algorithms:
        print(f"error: no algorithm.json found under {args.algorithms_dir}", file=sys.stderr)
        return 2

    run_batch(algorithms, instances, Path(args.instances_dir), Path(args.results_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
