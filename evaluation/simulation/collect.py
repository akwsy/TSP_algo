"""Collect per-algorithm quality metrics from the blind simulation scenarios."""
import json, os, re, sys, collections
from concurrent.futures import ThreadPoolExecutor
import run_sims as rs

OUT = sys.argv[1] if len(sys.argv) > 1 else "evaluation-data.json"
# cap/tl0 scenarios deliberately hit search limits, so exact is not a quality reference there.
LIMIT_FAMILIES = {"cap", "tl0"}

def one(job):
    fam, d, name, opts = job
    row = {"scenario": name, "family": fam, "algs": {}}
    for alg in rs.ALGS:
        rc, out, err = rs.run(alg, d, opts)
        if rc != 0: return None
        r = rs.parse(out)
        r["runtimeMs"] = float(re.search(r"Runtime: ([\d.]+) ms", out).group(1))
        r["states"] = int(re.search(r"candidates/states: (\d+)", out).group(1))
        row["algs"][alg] = {k: r[k] for k in ("status", "K", "N", "dist", "wait", "runtimeMs", "states")}
    return row

def main():
    jobs = []
    for n in sorted(os.listdir(rs.SC)):
        d = os.path.join(rs.SC, n); m = json.load(open(os.path.join(d, "meta.json")))
        fam = n.rsplit("_", 1)[0]
        if m["valid"] and fam not in LIMIT_FAMILIES and not n.startswith("invalid"):
            jobs.append((fam, d, n, m["opts"]))
    with ThreadPoolExecutor(8) as ex: rows = [r for r in ex.map(one, jobs) if r]
    stats = {a: collections.Counter() for a in rs.ALGS}
    sums = {a: collections.defaultdict(float) for a in rs.ALGS}
    fam = collections.defaultdict(lambda: {a: collections.Counter() for a in rs.ALGS})
    for row in rows:
        ex_ = row["algs"]["exact"]
        assert ex_["status"] == "OPTIMAL", row["scenario"]
        for a in rs.ALGS:
            r = row["algs"][a]
            same_visits = r["K"] == ex_["K"]
            optimal = same_visits and r["dist"] <= ex_["dist"] + 1e-6
            for c in (stats[a], fam[row["family"]][a]):
                c["n"] += 1; c["optimal"] += optimal; c["visits"] += r["K"]; c["bestVisits"] += ex_["K"]
                c["sameVisits"] += same_visits
            s = sums[a]
            s["runtime"] += r["runtimeMs"]; s["states"] += r["states"]; s["dist"] += r["dist"]
            if same_visits and ex_["dist"] > 1e-9: s["distRatio"] += r["dist"] / ex_["dist"]; s["distRatioN"] += 1
            s["maxRuntime"] = max(s["maxRuntime"], r["runtimeMs"])
    names = {"nearest": "Nearest neighbour (baseline)", "greedy": "Greedy insertion", "exact": "Branch and bound (exact)"}
    summary = []
    for a in rs.ALGS:
        c, s = stats[a], sums[a]; n = c["n"]
        summary.append({"id": a, "name": names[a], "scenarios": n,
            "optimalPct": 100 * c["optimal"] / n, "matchesBestVisitsPct": 100 * c["sameVisits"] / n,
            "visitsPctOfOptimal": 100 * c["visits"] / c["bestVisits"] if c["bestVisits"] else 100.0,
            "avgDistanceRatio": s["distRatio"] / s["distRatioN"] if s["distRatioN"] else 1.0,
            "avgRuntimeMs": s["runtime"] / n, "maxRuntimeMs": s["maxRuntime"], "avgStates": s["states"] / n})
    families = [{"family": f, "scenarios": v["exact"]["n"],
                 "optimalPct": {a: 100 * v[a]["optimal"] / v[a]["n"] for a in rs.ALGS},
                 "visitsPctOfOptimal": {a: (100 * v[a]["visits"] / v[a]["bestVisits"] if v[a]["bestVisits"] else 100.0) for a in rs.ALGS}}
                for f, v in sorted(fam.items())]
    json.dump({"scenarios": len(rows), "excludedFamilies": sorted(LIMIT_FAMILIES),
               "summary": summary, "families": families}, open(OUT, "w"), indent=1)
    print(json.dumps(summary, indent=1)); print(len(rows), "scenarios")
main()
