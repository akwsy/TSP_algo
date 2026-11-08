"""Aggregator: a pure function over run records. It knows nothing about experiments;
it groups by (algorithmId, sweep value) and by instanceId, so any experiment works. The sweep
value is record["sweepValue"] (with record["sweepParam"] naming what was varied); records
without it (older ones) are grouped by numCustomers, as "customers".

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
import random

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


def _sweep(record):
    if "sweepValue" in record:
        return record.get("sweepParam"), record["sweepValue"]
    return "customers", record["numCustomers"]


def aggregate(records, work_keys=DEFAULT_WORK_KEYS):
    best = _best_known(records)
    cells = {}
    for r in records:
        cells.setdefault((r["algorithmId"], _sweep(r)[1]), []).append(r)
    groups = []
    for (alg, value), runs in sorted(cells.items()):
        valid = [r for r in runs if r["valid"]]
        ratios = [r["visited"] / best[r["instanceId"]]["visited"]
                  if best[r["instanceId"]]["visited"] else 1.0 for r in valid]
        behind = [best[r["instanceId"]]["visited"] - r["visited"] for r in valid]
        found = [_work(r, work_keys) for r in runs]
        found = [(k, v) for k, v in found if k is not None]
        groups.append({
            "algorithmId": alg, "numCustomers": runs[0]["numCustomers"],
            "sweepParam": _sweep(runs[0])[0], "sweepValue": value, "runs": len(runs),
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
            "sweepValues": sorted({_sweep(r)[1] for r in records}),
            "algorithms": sorted({r["algorithmId"] for r in records}),
            "groups": groups,
            "bestKnown": sorted(best.values(), key=lambda b: (b["numCustomers"], b["instanceId"]))}


TIE_KM = 1e-9
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 12345
MAX_GAPS = 5


def _bootstrap_ci95(diffs):
    """95% percentile bootstrap interval of the mean: 2000 resamples drawn with
    random.Random(12345), so the same input always gives the same interval. Sorted resampled
    means m[0..1999]; the interval is [m[50], m[1949]]."""
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(diffs)
    means = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(BOOTSTRAP_RESAMPLES))
    return [means[int(0.025 * BOOTSTRAP_RESAMPLES)], means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]]


def _overlap(route_a, route_b):
    a, b = set(route_a or []) - {0}, set(route_b or []) - {0}
    return len(a & b) / len(a | b) if a | b else 1.0


def _pair(param, value, a, b, runs_a, runs_b):
    ids = sorted(set(runs_a) | set(runs_b))
    both = [i for i in ids if i in runs_a and i in runs_b and runs_a[i]["valid"] and runs_b[i]["valid"]]
    a_wins = b_wins = ties = 0
    diffs, dist_diffs, overlaps, gaps = [], [], [], []
    for i in both:
        ra, rb = runs_a[i], runs_b[i]
        d = ra["visited"] - rb["visited"]
        diffs.append(d)
        overlaps.append(_overlap(ra.get("route"), rb.get("route")))
        if d:
            gaps.append({"instanceId": i, "aVisited": ra["visited"], "bVisited": rb["visited"],
                         "difference": d})
        if d > 0:
            a_wins += 1
        elif d < 0:
            b_wins += 1
        else:
            dd = ra["distanceKm"] - rb["distanceKm"]
            dist_diffs.append(dd)
            if dd < -TIE_KM:
                a_wins += 1
            elif dd > TIE_KM:
                b_wins += 1
            else:
                ties += 1
    gaps.sort(key=lambda g: (-abs(g["difference"]), g["instanceId"]))
    return {"sweepParam": param, "sweepValue": value, "a": a, "b": b,
            "instances": len(both), "excluded": len(ids) - len(both),
            "aWins": a_wins, "bWins": b_wins, "ties": ties,
            "meanVisitDiff": _mean(diffs),
            "visitDiffCI95": _bootstrap_ci95(diffs) if diffs else None,
            "meanDistanceDiffWhenEqualVisits": _mean(dist_diffs),
            "meanOverlap": _mean(overlaps),
            "largestGaps": gaps[:MAX_GAPS]}


def pairwise(records):
    """Paired comparisons, pure. For each sweep value and each pair of algorithms (a, b) with
    a < b alphabetically, over the instances where BOTH runs are valid (`instances`; `excluded`
    counts the other instances either algorithm ran, dropped because a run failed).

    Scoring rule (the project's): more visits wins; equal visits and a distance shorter by more
    than 1e-9 km wins; otherwise a tie. aWins/bWins/ties count that over the paired instances.
    meanVisitDiff is the mean of (a visits - b visits); visitDiffCI95 is [low, high] from a
    deterministic bootstrap (_bootstrap_ci95). meanDistanceDiffWhenEqualVisits is the mean of
    (a km - b km) over instances with equal visits. meanOverlap is the mean Jaccard overlap of
    the sets of visited customer ids of the two routes (1.0 when both visit nobody).
    largestGaps: up to 5 instances with a non-zero visit difference, largest absolute
    difference first, ties by instanceId; `difference` is a minus b (signed).
    Means and intervals are null when no instance is paired. Output is sorted by sweep value,
    then a, then b."""
    cells = {}
    for r in records:
        param, value = _sweep(r)
        cells.setdefault((value, param), {}).setdefault(r["algorithmId"], {})[r["instanceId"]] = r
    pairs = []
    for (value, param), by_alg in sorted(cells.items(), key=lambda kv: kv[0][0]):
        algs = sorted(by_alg)
        for x, a in enumerate(algs):
            for b in algs[x + 1:]:
                pairs.append(_pair(param, value, a, b, by_alg[a], by_alg[b]))
    return pairs


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
