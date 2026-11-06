"""Aggregator: a pure function over run records. It knows nothing about experiments;
it groups by (algorithmId, numCustomers) and by instanceId, so any experiment works.

Definitions
- failure: record["valid"] is false. Failures are counted but left out of the
  visited / distance / total-minutes averages and the best-known comparison.
- timeout: record["status"] == "TIME_LIMIT" (the runner sets it when it kills the process).
  A timed-out run with a valid route counts as a timeout and still enters the averages.
- runtime and work cover every run that has the value (failures included).
- work: the first key of `work_keys` found as a number in record["stats"]
  (default nodesExpanded, then iterations). Runs without one are skipped; if none
  have one, mean is null, n is 0 and key is null.
- best known: per instance, the most visits any valid run achieved. It is only
  "optimalReported" when a valid OPTIMAL run reached that count. Nothing else is
  ever called optimal.
- bestKnownRatio: per valid run visited / best known (1.0 when best known is 0),
  averaged per group. visitsBehindBest: best known - visited, averaged.
- std is the sample standard deviation (n - 1), null when n < 2.
"""
import math

DEFAULT_WORK_KEYS = ("nodesExpanded", "iterations")


def _mean(values):
    return sum(values) / len(values) if values else None


def _std(values):
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _summary(values):
    return {"mean": _mean(values), "std": _std(values), "n": len(values)}


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _work(record, work_keys):
    stats = record.get("stats")
    if isinstance(stats, dict):
        for key in work_keys:
            if _is_number(stats.get(key)):
                return key, stats[key]
    return None, None


def _best_known(records):
    best = {}
    for r in records:
        if not r["valid"]:
            continue
        b = best.setdefault(r["instanceId"], {
            "instanceId": r["instanceId"], "numCustomers": r["numCustomers"],
            "visited": r["visited"], "achievedBy": [], "optimalReported": False})
        if r["visited"] > b["visited"]:
            b.update(visited=r["visited"], achievedBy=[], optimalReported=False)
        if r["visited"] == b["visited"]:
            if r["algorithmId"] not in b["achievedBy"]:
                b["achievedBy"].append(r["algorithmId"])
            if r["status"] == "OPTIMAL":
                b["optimalReported"] = True
    for b in best.values():
        b["achievedBy"].sort()
    return best


def aggregate(records, work_keys=DEFAULT_WORK_KEYS):
    best = _best_known(records)
    cells = {}
    for r in records:
        cells.setdefault((r["algorithmId"], r["numCustomers"]), []).append(r)
    groups = []
    for (alg, n), runs in sorted(cells.items()):
        valid = [r for r in runs if r["valid"]]
        ratios = [r["visited"] / best[r["instanceId"]]["visited"]
                  if best[r["instanceId"]]["visited"] else 1.0 for r in valid]
        behind = [best[r["instanceId"]]["visited"] - r["visited"] for r in valid]
        found = [_work(r, work_keys) for r in runs]
        found = [(k, v) for k, v in found if k is not None]
        groups.append({
            "algorithmId": alg, "numCustomers": n, "runs": len(runs),
            "failures": len(runs) - len(valid),
            "timeouts": sum(1 for r in runs if r["status"] == "TIME_LIMIT"),
            "optimalReports": sum(1 for r in valid if r["status"] == "OPTIMAL"),
            "visited": _summary([r["visited"] for r in valid]),
            "distanceKm": _summary([r["distanceKm"] for r in valid]),
            "totalMinutes": _summary([r["totalMinutes"] for r in valid]),
            "runtimeMs": _summary([r["runtimeMs"] for r in runs if _is_number(r.get("runtimeMs"))]),
            "bestKnownRatio": {"mean": _mean(ratios), "n": len(ratios)},
            "visitsBehindBest": {"mean": _mean(behind), "n": len(behind)},
            "work": {"mean": _mean([v for _, v in found]), "n": len(found),
                     "key": found[0][0] if found else None},
        })
    return {"sizes": sorted({r["numCustomers"] for r in records}),
            "algorithms": sorted({r["algorithmId"] for r in records}),
            "groups": groups,
            "bestKnown": sorted(best.values(), key=lambda b: (b["numCustomers"], b["instanceId"]))}
