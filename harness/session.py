"""Session: one algorithm on one instance, called once per day until every place is visited.

Saved layout (stable; later tickets build on it). One JSON file per session:

    <results-dir>/sessions/<algorithmId>__<instanceId>__<runId>.json

    {
      "algorithmId", "commit", "fingerprint", "instanceId", "instanceHash", "seed",
      "numCustomers", "experiment", "runId", "timestamp",
      "formatVersion": SESSION_FORMAT_VERSION when the session was run (see below),
      "maxDays":       the day cap in force when it was run (30 unless --max-days says otherwise),
      "outcome":       "finished" | "did not finish",
      "stopReason":    null when finished, else one of STOP_REASONS (listed below),
      "stopDay":       null when finished, else the day number the session stopped on
                       (for day_limit: the last day run, i.e. 30),
      "explanation":   null when finished, else plain words naming the day and the reason,
      "partialFigures": true when the session did not finish. visitedSoFar, workingMinutes,
                       totalDistanceKm and finalReturnMinute are then informational progress
                       figures and must NEVER be used or shown as a finishing time,
      "unvisitedAtStop": places still unvisited when the session stopped (0 if finished),
      "days":                  number of days run (including a stopped one that produced no route),
      "visitedSoFar":          places visited over all valid days,
      "workingMinutes":        sum over days with a valid route that visited new places of
                               day_working_minutes(). Finished session: the last day counts only
                               until its last place is served. Stopped session: every counted day
                               is a completed day and counts until its return to the depot (the
                               stopped day adds nothing),
      "totalDistanceKm", "totalRuntimeMs", "finalReturnMinute" (last counted day's return to depot),
      "dayRecords": [ {         one per day, in order
          "day": 1.., "instanceId": "<id>" or "<id>-dayN", "numPlaces": customers given that day,
          "route": [0, ...original place ids..., 0], "status", "killed", "runtimeMs", "stats",
          "valid", "failureReason", "failureKind" (one of harness.run.FAILURE_KINDS, null when
          valid; absent on sessions saved before it existed), "visited": [original ids newly visited that day],
          "distanceKm", "returnMinute", "workingMinutes" (null on a day that failed or visited
          nothing), "schedule": [{id (original), arriveMinute, startMinute, leaveMinute}] } ]
    }

Stop reasons (STOP_REASONS; stable). Explanation texts, N = day, K = places still unvisited:

    no_progress       "Stopped on day N: the algorithm visited no new places (K still unvisited)"
    day_limit         "Stopped after day 30: K place(s) still unvisited (day limit reached)"
    crashed           "Stopped on day N: the algorithm crashed (<detail, e.g. exited with code 3>)"
    invalid_route     "Stopped on day N: the algorithm gave an invalid route (<detail>)"
    unreadable_output "Stopped on day N: the algorithm's output could not be read (<detail>)"
    timed_out         "Stopped on day N: the algorithm ran out of time (<detail>) and gave no usable answer"
    could_not_start   "Stopped on day N: the algorithm could not be started (<detail>)"

A day killed by the time limit that had already printed a complete valid route is scored by the
runner's normal rules (status TIME_LIMIT, killed true): it is progress if the route is valid and
visits new places, otherwise no_progress or invalid_route. Only a timeout with no usable route is
timed_out. The day cap is 30 (MAX_DAYS); a different cap can be passed explicitly (run_session's `max_days`,
the experiment command's advanced `--max-days N`) and is part of the saved-session reuse key.

Day 1 is the ordinary first-day run (a saved first-day record may be passed in and is reused).
Later days get sub_instance(): only the unvisited places plus the depot (id 0), customers
renumbered consecutively in original order, same seed, speed, departure and deadline.
"""
from datetime import datetime, timezone

from .run import make_record

MAX_DAYS = 30
# Version of everything that decides what a session's result is, apart from the algorithm code and
# the instance: the session logic (stop rules, sub-instances, how days are scored), the record
# layout and the working-hours definition. Bump it whenever one of those changes. It is part of
# the reuse key (see sessionstore.py), so saved sessions of an older version are run again.
SESSION_FORMAT_VERSION = 1
STOP_REASONS = ("no_progress", "day_limit", "crashed", "invalid_route", "unreadable_output",
                "timed_out", "could_not_start")


def _kind_from_text(entry):
    """Failure kind guessed from the message, for day records saved before `failureKind` existed."""
    reason = entry["failureReason"] or "unknown failure"
    if entry["killed"]:
        return "timed_out"
    if reason.startswith("could not start"):
        return "could_not_start"
    if reason.startswith("exited with code"):
        return "crashed"
    if reason.startswith(("output is not", "status must", "unknown status", "stats must")):
        return "unreadable_output"
    return "invalid_route"


def classify_failure(entry):
    """(stop reason, explanation phrase) for a day record that gave no usable route.

    Uses the record's `failureKind` (set by the runner; harness/run.py). Only records without it
    (saved by an older harness) fall back to matching the message text."""
    reason = entry["failureReason"] or "unknown failure"
    kind = entry.get("failureKind") or _kind_from_text(entry)
    if kind == "timed_out":
        return kind, f"the algorithm ran out of time ({reason}) and gave no usable answer"
    if kind == "could_not_start":
        return kind, f"the algorithm could not be started ({reason.split(': ', 1)[-1]})"
    if kind == "crashed":
        return kind, f"the algorithm crashed ({reason})"
    if kind == "unreadable_output":
        return kind, f"the algorithm's output could not be read ({reason})"
    return "invalid_route", f"the algorithm gave an invalid route ({reason})"


def day_working_minutes(result, departure, final):
    """Working minutes of one day from a validator result: from the departure until back at the
    depot (travelling plus waiting); on the final day only until the last place is served."""
    if final:
        return result["schedule"][-1]["startMinute"] - departure
    return result["returnMinute"] - departure


def total_working_minutes(results, departure):
    """Sum over days; the last result is the final day. Nights and idle time are not counted."""
    return sum(day_working_minutes(r, departure, final=(i == len(results) - 1))
               for i, r in enumerate(results))


def sub_instance(instance, unvisited, day):
    """Problem for `day`: depot plus the unvisited places. Returns (instance, original ids)."""
    ids = [0] + sorted(unvisited)
    locations = [{**instance["locations"][old], "id": new} for new, old in enumerate(ids)]
    matrix = [[instance["distanceKm"][a][b] for b in ids] for a in ids]
    sub = {**instance, "instanceId": f"{instance['instanceId']}-day{day}",
           "locations": locations, "distanceKm": matrix}
    return sub, ids


def _day_record(day, instance_id, ids, record):
    """Day entry from a make_record record, with ids mapped back to original place ids."""
    back = ids.__getitem__
    valid = record["valid"]
    route = record["route"]
    return {
        "day": day, "instanceId": instance_id, "numPlaces": len(ids) - 1,
        "route": [back(i) for i in route] if valid else route,
        "status": record["status"], "killed": record["killed"], "runtimeMs": record["runtimeMs"],
        "stats": record["stats"], "valid": valid, "failureReason": record["failureReason"],
        "failureKind": record.get("failureKind"),
        "visited": [back(s["id"]) for s in record["schedule"]] if valid else [],
        "distanceKm": record["distanceKm"], "returnMinute": record["returnMinute"],
        "schedule": [{**s, "id": back(s["id"])} for s in record["schedule"]] if valid else None,
    }


def run_session(meta, instance, run_id, first_day=None, max_days=None):
    """Run the algorithm day by day on `instance` until everything is visited.

    `first_day` is the saved first-day record for this algorithm and instance, used as day 1
    when given (so nothing is computed twice). Returns the session record (see module doc).
    Seam: ticket 03 decides whether a saved session is reused and indexes it."""
    max_days = max_days or MAX_DAYS
    unvisited = set(range(1, len(instance["locations"])))
    days = []
    stop = None
    day = 0
    while unvisited:
        day += 1
        if day > max_days:
            n = len(unvisited)
            stop = ("day_limit", max_days, f"Stopped after day {max_days}: {n} "
                    f"{'place' if n == 1 else 'places'} still unvisited (day limit reached)")
            break
        if day == 1:
            sub, ids = instance, list(range(len(instance["locations"])))
            record = first_day or make_record(meta, sub, run_id)
        else:
            sub, ids = sub_instance(instance, unvisited, day)
            record = make_record(meta, sub, run_id)
        entry = _day_record(day, sub["instanceId"], ids, record)
        days.append(entry)
        if not entry["valid"]:
            entry["workingMinutes"] = None
            reason, phrase = classify_failure(entry)
            stop = (reason, day, f"Stopped on day {day}: {phrase}")
            break
        if not entry["visited"]:
            entry["workingMinutes"] = None
            stop = ("no_progress", day, f"Stopped on day {day}: the algorithm visited no new places "
                                        f"({len(unvisited)} still unvisited)")
            break
        unvisited -= set(entry["visited"])
        entry["workingMinutes"] = day_working_minutes(
            {"returnMinute": entry["returnMinute"], "schedule": entry["schedule"]},
            instance["departureMinute"], final=not unvisited)
    good = [d for d in days if d["valid"] and d["visited"]]
    return {
        "algorithmId": meta["id"], "commit": meta["_commit"], "fingerprint": meta.get("_fingerprint"),
        "instanceId": instance["instanceId"], "seed": instance.get("seed"),
        "numCustomers": len(instance["locations"]) - 1, "runId": run_id,
        "formatVersion": SESSION_FORMAT_VERSION, "maxDays": max_days,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": "did not finish" if stop else "finished",
        "stopReason": stop[0] if stop else None, "stopDay": stop[1] if stop else None,
        "explanation": stop[2] if stop else None,
        "partialFigures": bool(stop), "unvisitedAtStop": len(unvisited),
        "days": len(days), "visitedSoFar": sum(len(d["visited"]) for d in good),
        "workingMinutes": sum(d["workingMinutes"] for d in good),
        "totalDistanceKm": sum(d["distanceKm"] for d in good),
        "totalRuntimeMs": sum(d["runtimeMs"] for d in days),
        "finalReturnMinute": good[-1]["returnMinute"] if good else None,
        "dayRecords": days,
    }
