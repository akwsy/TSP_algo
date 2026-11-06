"""Runner: python3 -m harness.run --seeds 1 2 3 [options]

Runs every algorithm found in algorithms/*/algorithm.json on the same generated
instances, validates each answer, and writes one result JSON per run plus
results/index.json.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import ConfigError, InstanceConfig
from .dataset import DatasetError, load_places
from .generate_instance import DEFAULT_DATASET
from .instance import build_instance
from .validator import failure_result, validate_route

ROOT = Path(__file__).resolve().parent.parent
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
    """Run the algorithm once; return (output dict or None, runtimeMs, error or None, stderr, timedOut)."""
    limit = meta.get("timeLimitSeconds", 10)
    start = time.perf_counter()
    try:
        proc = subprocess.run(meta["command"], cwd=meta["_dir"], input=json.dumps({**instance, "timeLimitSeconds": limit}).encode("utf-8"),
                              capture_output=True, timeout=limit)
    except OSError as exc:
        runtime_ms = (time.perf_counter() - start) * 1000
        return None, runtime_ms, f"could not start the command: {exc.strerror or exc}", "", False
    except subprocess.TimeoutExpired as exc:
        runtime_ms = (time.perf_counter() - start) * 1000
        error = f"exceeded the time limit of {limit} s and was killed"
        output, _ = parse_output(_text(exc.stdout)) if _text(exc.stdout).strip() else (None, None)
        if output is not None:
            output["status"] = "TIME_LIMIT"
        return output, runtime_ms, error, _text(exc.stderr), True
    runtime_ms = (time.perf_counter() - start) * 1000
    if proc.returncode != 0:
        return None, runtime_ms, f"exited with code {proc.returncode}", _text(proc.stderr), False
    output, error = parse_output(_text(proc.stdout))
    return output, runtime_ms, error, _text(proc.stderr), False


def make_record(meta, instance, run_id):
    output, runtime_ms, error, stderr, timed_out = execute(meta, instance)
    output = output or {}
    route = output.get("route")
    status = "TIME_LIMIT" if timed_out else output.get("status")
    if error and not (timed_out and route is not None):
        checked = failure_result(error)
    else:
        checked = validate_route(instance, route)
    record = {
        "algorithmId": meta["id"],
        "commit": meta["_commit"],
        "instanceId": instance["instanceId"],
        "seed": instance.get("seed"),
        "numCustomers": len(instance["locations"]) - 1,
        "runId": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "route": route,
        "runtimeMs": runtime_ms,
        "stats": output.get("stats"),
        "stderr": stderr,
    }
    record.update({k: checked[k] for k in RESULT_FIELDS})
    return record


def run_batch(algorithms, instances, instances_dir, results_dir, extra=None):
    """Run every algorithm on every instance; write instances, one result file per run and
    results/index.json. `extra` (e.g. {"experiment": "scaling"}) is added to each record and
    index entry. Returns the list of records."""
    instances_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    for inst in instances:
        (instances_dir / f"{inst['instanceId']}.json").write_text(
            json.dumps(inst, indent=2) + "\n", encoding="utf-8")

    index_path = results_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"runs": []}
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    records = []
    for meta in algorithms:
        for inst in instances:
            record = make_record(meta, inst, run_id)
            record.update(extra or {})
            records.append(record)
            name = f"{record['algorithmId']}__{record['instanceId']}__{run_id}.json"
            (results_dir / name).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            index["runs"].append({
                "file": name, "runId": run_id, "algorithmId": record["algorithmId"],
                "commit": record["commit"], "instanceId": record["instanceId"],
                "numCustomers": record["numCustomers"], "seed": record["seed"],
                "timestamp": record["timestamp"], "status": record["status"],
                "valid": record["valid"], "visited": record["visited"],
                "distanceKm": record["distanceKm"], "runtimeMs": record["runtimeMs"],
                "failureReason": record["failureReason"], **(extra or {})})
            print(f"{record['algorithmId']} on {record['instanceId']}: "
                  f"{'valid, visited ' + str(record['visited']) if record['valid'] else 'FAILED: ' + str(record['failureReason'])}",
                  flush=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m harness.run",
                                 description="Run all algorithms on the same generated instances.")
    ap.add_argument("--seeds", type=int, nargs="+", required=True, help="one instance per seed")
    ap.add_argument("--customers", type=int, default=10)
    ap.add_argument("--departure", type=int, default=360)
    ap.add_argument("--period", type=int, default=480)
    ap.add_argument("--speed", type=float, default=40.0)
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
