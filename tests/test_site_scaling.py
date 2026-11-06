"""Scaling-chart and run-history logic (site/js/lib/scaling.js), run under node. Skipped when node is missing."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "site" / "js" / "lib" / "scaling.js"


def call(fn, *args):
    script = (f"import * as m from {json.dumps(MODULE.as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def grp(alg, n, mean, std=None, metric="visited", work=None):
    g = {"algorithmId": alg, "numCustomers": n, metric: {"mean": mean, "std": std, "n": 3}}
    if work is not None:
        g["work"] = work
    return g


def run(alg, inst, commit, ts, visited=3, dist=10.0, ms=5.0, valid=True):
    return {"algorithmId": alg, "instanceId": inst, "commit": commit, "timestamp": ts,
            "valid": valid, "visited": visited if valid else None,
            "distanceKm": dist if valid else None, "runtimeMs": ms}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ScalingTest(unittest.TestCase):
    def test_series_per_algorithm_sorted_with_bands(self):
        s = call("buildSeries", [grp("b", 10, 5, 1), grp("a", 10, 4, 0.5), grp("a", 5, 3, 0.25)], "visited")
        self.assertEqual([x["algorithmId"] for x in s], ["a", "b"])
        self.assertEqual([p["x"] for p in s[0]["points"]], [5, 10])
        self.assertEqual((s[0]["points"][1]["lo"], s[0]["points"][1]["hi"]), (3.5, 4.5))

    def test_null_std_gives_no_band_and_null_mean_is_dropped_not_zero(self):
        s = call("buildSeries", [grp("a", 5, 3, None), grp("a", 10, None, None)], "visited")
        self.assertEqual(len(s[0]["points"]), 1)
        self.assertIsNone(s[0]["points"][0]["lo"])
        self.assertEqual(call("buildSeries", [grp("a", 5, None)], "visited"), [])

    def test_loglog_skips_zero_and_missing_work_and_keeps_key(self):
        groups = [grp("a", 5, 1, metric="runtimeMs", work={"mean": 10, "n": 3, "key": "nodesExpanded"}),
                  grp("a", 10, 1, metric="runtimeMs", work={"mean": None, "n": 0, "key": None}),
                  grp("b", 5, 1, metric="runtimeMs", work={"mean": 0, "n": 3, "key": "iterations"})]
        s = {x["algorithmId"]: x for x in call("logLogSeries", groups, "work")}
        self.assertEqual(s["a"]["key"], "nodesExpanded")
        self.assertEqual(len(s["a"]["points"]), 1)
        self.assertEqual(s["a"]["skipped"], [10])
        self.assertEqual(s["b"]["points"], [])
        self.assertIsNone(s["a"]["slope"])

    def test_fit_slope_recovers_exponent(self):
        pts = [{"x": n, "y": 3 * n ** 2} for n in (5, 10, 20)]
        self.assertAlmostEqual(call("fitSlope", pts), 2.0, places=6)
        self.assertIsNone(call("fitSlope", [{"x": 5, "y": 1}]))

    def test_declared_exponent(self):
        self.assertEqual(call("declaredExponent", "O(n^2)"), 2)
        self.assertEqual(call("declaredExponent", "O(1)"), 0)
        self.assertEqual(call("declaredExponent", "O(n log n)"), 1)
        self.assertIsNone(call("declaredExponent", "O(2^n)"))
        self.assertIsNone(call("declaredExponent", None))

    def test_history_groups_by_algorithm_and_commit_newest_first(self):
        runs = [run("a", "i1", "c1", "2026-01-01T00:00:00"), run("a", "i2", "c1", "2026-01-01T00:01:00"),
                run("a", "i1", "c2", "2026-02-01T00:00:00"), run("a", "i1", None, "2026-03-01T00:00:00", valid=False)]
        g = call("groupRunsByCommit", runs)
        self.assertEqual([x["commit"] for x in g], [None, "c2", "c1"])
        self.assertEqual(len(g[2]["runs"]), 2)
        self.assertEqual(g[0]["valid"], 0)

    def test_compare_uses_shared_instances_and_latest_run(self):
        a = [run("x", "i1", "c1", "t1", visited=3, ms=10), run("x", "i2", "c1", "t1", visited=5, ms=10),
             run("x", "i9", "c1", "t1")]
        b = [run("x", "i1", "c2", "t2", visited=4, ms=20), run("x", "i1", "c2", "t3", visited=5, ms=20),
             run("x", "i2", "c2", "t2", valid=False)]
        c = call("compareVersions", a, b)
        self.assertEqual(c["sharedInstances"], 2)
        self.assertEqual((c["onlyA"], c["onlyB"]), (1, 0))
        self.assertEqual(c["failedB"], 1)
        self.assertEqual(c["visited"], {"a": 3, "b": 5, "delta": 2, "n": 1})
        self.assertEqual(c["runtimeMs"]["delta"], 2.5)

    def test_compare_with_no_overlap(self):
        c = call("compareVersions", [run("x", "i1", "c1", "t")], [run("x", "i2", "c2", "t")])
        self.assertEqual(c["sharedInstances"], 0)
        self.assertIsNone(c["visited"]["a"])


if __name__ == "__main__":
    unittest.main()
