"""Website data logic (site/js/lib/model.js), run under node. Skipped when node is missing."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "site" / "js" / "lib" / "model.js"


def call(fn, *args):
    script = (f"import * as m from {json.dumps(MODEL.as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def grp(alg, visited, dist, failures=0, n=10):
    return {"algorithmId": alg, "numCustomers": n, "runs": 5, "failures": failures,
            "visited": {"mean": visited}, "distanceKm": {"mean": dist}}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ModelTest(unittest.TestCase):
    def test_ranks_by_visits_then_shorter_distance(self):
        rows = call("rankGroups", [grp("a", 4, 50), grp("b", 6, 90), grp("c", 6, 70)])
        self.assertEqual([r["algorithmId"] for r in rows], ["c", "b", "a"])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3])

    def test_exact_ties_share_a_rank(self):
        rows = call("rankGroups", [grp("a", 5, 10), grp("b", 5, 10), grp("c", 3, 1)])
        self.assertEqual([r["rank"] for r in rows], [1, 1, 3])

    def test_algorithm_with_no_valid_runs_is_last_not_zero_visits(self):
        rows = call("rankGroups", [grp("dead", None, None, failures=5), grp("low", 0, 0)])
        self.assertEqual([r["algorithmId"] for r in rows], ["low", "dead"])
        self.assertIsNone(rows[1]["rank"])

    def test_algorithms_with_failed_runs_rank_below_fully_valid_ones(self):
        rows = call("rankGroups", [grp("flaky", 9, 10, failures=2), grp("solid", 4, 90),
                                   grp("solid2", 4, 50), grp("flaky2", 9, 5, failures=1)])
        self.assertEqual([r["algorithmId"] for r in rows], ["solid2", "solid", "flaky2", "flaky"])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3, 4])
        self.assertEqual([r["rankedBelow"] for r in rows], [0, 0, 1, 2])

    def test_overview_badges_explain_failures_ranking_and_contradicted_optimal(self):
        g = {**grp("a", 5, 10, failures=2), "timeouts": 1, "selfReportedTimeLimit": 3, "contradictedOptimal": 1}
        flags = call("groupBadges", g)
        self.assertEqual([(f["tone"], f["text"]) for f in flags], [
            ("bad", "2 of 5 failed, 1 killed for time"),
            ("warn", "ranked below: 2 failed runs"),
            ("note", "3 reported TIME_LIMIT"),
            ("warn", "OPTIMAL claim contradicted in 1 run")])
        self.assertEqual(call("groupBadges", grp("b", 5, 10)), [{"tone": "ok", "text": "none"}])
        # old aggregate files lack the newer counters
        self.assertEqual(call("groupBadges", grp("b", 5, 10, failures=1))[1]["text"], "ranked below: 1 failed run")

    def test_classifies_failures_in_plain_words(self):
        def k(status, reason):
            return call("failureKind", {"status": status, "failureReason": reason})
        self.assertEqual(k("TIME_LIMIT", "exceeded the time limit of 1 s and was killed"), "timed out")
        self.assertEqual(call("failureKind", {"status": "TIME_LIMIT", "killed": True, "valid": True}), "timed out")
        self.assertEqual(call("failureKind", {"status": "TIME_LIMIT", "killed": False, "valid": False,
                                              "failureReason": "route repeats a customer"}), "invalid")
        self.assertEqual(k(None, "exited with code 3"), "crashed")
        self.assertEqual(k("HEURISTIC", "route repeats a customer"), "invalid")

    def test_failure_list_includes_invalid_and_harness_killed_only(self):
        runs = [{"valid": True, "status": "HEURISTIC", "file": "ok"},
                {"valid": False, "status": "HEURISTIC", "file": "bad"},
                {"valid": True, "status": "TIME_LIMIT", "killed": True, "file": "slow"},
                {"valid": True, "status": "TIME_LIMIT", "killed": False, "file": "own-limit"},
                {"valid": False, "status": "TIME_LIMIT", "file": "old-killed",
                 "failureReason": "exceeded the time limit of 1 s and was killed"}]
        self.assertEqual([r["file"] for r in call("failedRuns", runs)], ["bad", "slow", "old-killed"])

    def test_short_commit_keeps_the_dirty_marker(self):
        h = "0123456789abcdef0123456789abcdef01234567"
        self.assertEqual(call("shortCommit", h, 7), "0123456")
        self.assertEqual(call("shortCommit", h + "+dirty", 7), "0123456+dirty")
        self.assertIsNone(call("shortCommit", None, 7))
