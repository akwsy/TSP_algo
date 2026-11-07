"""Aggregator: a pure function over run records. It knows nothing about experiments;
it groups by (algorithmId, numCustomers) and by instanceId, so any experiment works.

Definitions
- failure: record["valid"] is false. Failures are counted but left out of the
  visited / distance / total-minutes averages and the best-known comparison.
- timeout: a run the harness killed for exceeding the time limit (record["killed"] is true,
  or, for older records, the failureReason ends "was killed"). A killed run that had already
  printed a valid route counts as a timeout and still enters the averages.
- selfReportedTimeLimit: a valid run the algorithm itself reported as status TIME_LIMIT
  without being killed. That is an ordinary valid result, not a timeout or failure.
- contradictedOptimal: valid runs that claimed OPTIMAL but visited fewer customers than the
  best known for that instance, so the claim is demonstrably wrong. Invalid runs make no claim.
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


def _killed(record):
    if "killed" in record:
        return bool(record["killed"])
    return str(record.get("failureReason") or "").endswith("was killed")


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
            "timeouts": sum(1 for r in runs if _killed(r)),
            "selfReportedTimeLimit": sum(1 for r in valid if r["status"] == "TIME_LIMIT" and not _killed(r)),
            "contradictedOptimal": sum(1 for r in valid if r["status"] == "OPTIMAL"
                                       and r["visited"] < best[r["instanceId"]]["visited"]),
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


def aggregate_sessions(sessions):
    """Full-run aggregate over session records (layout: harness/session.py). Pure.

    Definitions
    - Only FINISHED sessions (outcome "finished") enter any mean/std; a stopped session
      is counted with its stop reason and is never treated as a time.
    - workingHours = workingMinutes / 60 (hours, not minutes). days, totalDistanceKm (km) and
      totalRuntimeMs (compute time, ms) are summarised the same way: {mean, std, n}, std sample
      (n - 1), null when n < 2; mean null when n is 0.
    - instances per size = distinct instanceIds seen at that size (instancesPerSize, keyed by
      the size as a string); unfinished = instances - finished.

    Ranking rule, per size (ranking[*].entries, in display order):
      1. algorithms that finished every instance at that size, by mean working hours (fewer
         first), exact ties by shorter mean total distance, then by algorithm id;
      2. algorithms with some but not all instances finished, ordered the same way by the means
         over their finished instances;
      3. algorithms with no finished instance last, by algorithm id, with rank null.
      Ranked entries get rank 1, 2, ... in that order; each entry carries finishedAll and
      unfinished (count of instances not finished).
    Overall (overall): per algorithm the average of its per-size ranks, an unranked size
    counting as (number of algorithms + 1); lower is better, ties by algorithm id.
    """
    cells = {}
    inst = {}
    for r in sessions:
        cells.setdefault((r["algorithmId"], r["numCustomers"]), []).append(r)
        inst.setdefault(r["numCustomers"], set()).add(r["instanceId"])
    groups = []
    for (alg, n), runs in sorted(cells.items()):
        done = [r for r in runs if r["outcome"] == "finished"]
        reasons = {}
        for r in runs:
            if r["outcome"] != "finished":
                reasons[r["stopReason"]] = reasons.get(r["stopReason"], 0) + 1
        groups.append({
            "algorithmId": alg, "numCustomers": n, "instances": len(inst[n]),
            "finished": len(done), "stopped": len(runs) - len(done),
            "stopReasons": dict(sorted(reasons.items())),
            "workingHours": _summary([r["workingMinutes"] / 60 for r in done]),
            "days": _summary([r["days"] for r in done]),
            "totalDistanceKm": _summary([r["totalDistanceKm"] for r in done]),
            "totalRuntimeMs": _summary([r["totalRuntimeMs"] for r in done]),
        })
    algs = sorted({g["algorithmId"] for g in groups})
    ranking = []
    for n in sorted(inst):
        gs = [g for g in groups if g["numCustomers"] == n]
        order = sorted(gs, key=lambda g: (
            g["finished"] == 0, g["finished"] < g["instances"],
            g["workingHours"]["mean"] if g["finished"] else 0,
            g["totalDistanceKm"]["mean"] if g["finished"] else 0, g["algorithmId"]))
        entries, rank = [], 0
        for g in order:
            if g["finished"]:
                rank += 1
            entries.append({
                "rank": rank if g["finished"] else None, "algorithmId": g["algorithmId"],
                "finishedAll": g["finished"] == g["instances"],
                "unfinished": g["instances"] - g["finished"], "finished": g["finished"],
                "workingHours": g["workingHours"], "totalDistanceKm": g["totalDistanceKm"]})
        ranking.append({"numCustomers": n, "instances": len(inst[n]), "entries": entries})
    last = len(algs) + 1
    overall = []
    for a in algs:
        ranks = [next((e["rank"] for e in rk["entries"] if e["algorithmId"] == a), None)
                 for rk in ranking]
        ranks = [last if x is None else x for x in ranks]
        overall.append({"algorithmId": a, "averageRank": sum(ranks) / len(ranks)})
    overall.sort(key=lambda o: (o["averageRank"], o["algorithmId"]))
    return {"sizes": sorted(inst), "algorithms": algs,
            "instancesPerSize": {str(n): len(inst[n]) for n in sorted(inst)},
            "groups": groups, "ranking": ranking, "overall": overall}
