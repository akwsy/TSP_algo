"""Session: one algorithm on one instance, called once per day until every place is visited.

Saved layout (stable; later tickets build on it). One JSON file per session:

    <results-dir>/sessions/<algorithmId>__<instanceId>__<runId>.json

    {
      "algorithmId", "commit", "fingerprint", "instanceId", "instanceHash", "seed",
      "numCustomers", "experiment", "runId", "timestamp",
      "outcome":       "finished" | "did not finish",
      "stopReason":    null | "no_progress" | "day_limit" | "algorithm_failed",   (ticket 02 refines)
      "stopDay":       null | day number the session stopped on,
      "explanation":   plain words, e.g. "Stopped on day 3: the algorithm crashed" (null if finished),
      "days":                  number of days run (including a stopped one that produced no route),
      "visitedSoFar":          places visited over all valid days,
      "workingMinutes":        total working minutes so far (see day_working_minutes),
      "totalDistanceKm", "totalRuntimeMs", "finalReturnMinute" (last valid day's return to depot),
      "dayRecords": [ {         one per day, in order
          "day": 1.., "instanceId": "<id>" or "<id>-dayN", "numPlaces": customers given that day,
          "route": [0, ...original place ids..., 0], "status", "killed", "runtimeMs", "stats",
          "valid", "failureReason", "visited": [original ids newly visited that day],
          "distanceKm", "returnMinute", "workingMinutes", "schedule": [{id (original), arriveMinute,
          startMinute, leaveMinute}] } ]
    }

Day 1 is the ordinary first-day run (a saved first-day record may be passed in and is reused).
Later days get sub_instance(): only the unvisited places plus the depot (id 0), customers
renumbered consecutively in original order, same seed, speed, departure and deadline.
"""
from datetime import datetime, timezone

from .run import make_record

MAX_DAYS = 30


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
        "visited": [back(s["id"]) for s in record["schedule"]] if valid else [],
        "distanceKm": record["distanceKm"], "returnMinute": record["returnMinute"],
        "schedule": [{**s, "id": back(s["id"])} for s in record["schedule"]] if valid else None,
    }


def run_session(meta, instance, run_id, first_day=None, max_days=MAX_DAYS):
    """Run the algorithm day by day on `instance` until everything is visited.

    `first_day` is the saved first-day record for this algorithm and instance, used as day 1
    when given (so nothing is computed twice). Returns the session record (see module doc).
    Seams: ticket 02 replaces the minimal stop handling below with full reasons and texts;
    ticket 03 decides whether a saved session is reused and indexes it."""
    unvisited = set(range(1, len(instance["locations"])))
    days, results = [], []
    stop = None
    day = 0
    while unvisited:
        day += 1
        if day > max_days:
            stop = ("day_limit", max_days, f"Stopped after {max_days} days with places still unvisited")
            break
        if day == 1:
            sub, ids = instance, list(range(len(instance["locations"])))
            record = first_day or make_record(meta, sub, run_id)
        else:
            sub, ids = sub_instance(instance, unvisited, day)
            record = make_record(meta, sub, run_id)
        entry = _day_record(day, sub["instanceId"], ids, record)
        if not entry["valid"]:
            days.append(entry)
            stop = ("algorithm_failed", day, f"Stopped on day {day}: {entry['failureReason']}")
            break
        if not entry["visited"]:
            days.append(entry)
            stop = ("no_progress", day, f"Stopped on day {day}: no new places were visited")
            break
        unvisited -= set(entry["visited"])
        final = not unvisited
        entry["workingMinutes"] = day_working_minutes(
            {"returnMinute": entry["returnMinute"], "schedule": entry["schedule"]},
            instance["departureMinute"], final)
        days.append(entry)
        results.append(entry)
    good = [d for d in days if d["valid"] and d["visited"]]
    return {
        "algorithmId": meta["id"], "commit": meta["_commit"], "fingerprint": meta.get("_fingerprint"),
        "instanceId": instance["instanceId"], "seed": instance.get("seed"),
        "numCustomers": len(instance["locations"]) - 1, "runId": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": "did not finish" if stop else "finished",
        "stopReason": stop[0] if stop else None, "stopDay": stop[1] if stop else None,
        "explanation": stop[2] if stop else None,
        "days": len(days), "visitedSoFar": sum(len(d["visited"]) for d in good),
        "workingMinutes": sum(d["workingMinutes"] for d in good),
        "totalDistanceKm": sum(d["distanceKm"] for d in good),
        "totalRuntimeMs": sum(d["runtimeMs"] for d in days),
        "finalReturnMinute": good[-1]["returnMinute"] if good else None,
        "dayRecords": days,
    }
