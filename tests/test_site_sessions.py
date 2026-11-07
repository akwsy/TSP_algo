"""Full-run session listing logic (site/js/lib/sessions.js), run under node. Skipped when node is missing."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "site" / "js" / "lib" / "sessions.js"


def call(fn, *args):
    script = (f"import * as m from {json.dumps(MODULE.as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def sess(alg="a", inst="n5-seed1", n=5, seed=1, outcome="did not finish", ts="2026-01-02T10:00:00+00:00",
         file=None, minutes=90, visited=3, day=2, days=2, dist=10.0, reason="no_progress", commit=None):
    done = outcome == "finished"
    return {"file": file or f"sessions/{alg}__{inst}__{ts}.json", "algorithmId": alg, "instanceId": inst,
            "numCustomers": n, "seed": seed, "timestamp": ts, "outcome": outcome, "commit": commit,
            "stopReason": None if done else reason, "stopDay": None if done else day, "days": days,
            "visitedSoFar": n if done else visited, "workingMinutes": minutes,
            "unvisitedAtStop": 0 if done else n - visited, "totalDistanceKm": dist}


def run(alg, inst, ts, valid=False, reason="exited with code 1"):
    return {"algorithmId": alg, "instanceId": inst, "timestamp": ts, "valid": valid, "failureReason": reason,
            "file": f"{alg}__{inst}.json"}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SessionsTest(unittest.TestCase):
    def test_missing_index_is_empty(self):
        self.assertEqual(call("sessionsOf", None), [])
        self.assertEqual(call("sessionsOf", {}), [])

    def test_example_words_have_no_jargon(self):
        self.assertEqual(call("exampleWords", sess(seed=3, n=10)), "Example 3 with 10 places")
        self.assertEqual(call("exampleWords", sess(seed=1, n=1)), "Example 1 with 1 place")

    def test_partial_text_converts_minutes_and_is_labelled(self):
        t = call("partialText", sess(visited=3, n=5, minutes=150))
        self.assertEqual(t, "3 of 5 places visited so far, 2.5 working hours so far (so far, not a finishing time)")

    def test_merge_lists_stopped_only_and_sorts_newest_first(self):
        runs = [run("a", "n5-seed1", "2026-01-01T00:00:00+00:00")]
        ss = [sess(ts="2026-01-03T00:00:00+00:00"), sess(outcome="finished", inst="n5-seed2")]
        items = call("mergeFailures", runs, ss)
        self.assertEqual([i["type"] for i in items], ["session", "run"])
        self.assertEqual(items[0]["kind"], "did not finish every place")
        self.assertEqual(items[1]["kind"], "crashed")

    def test_filter_by_kind_and_algorithm(self):
        items = call("mergeFailures", [run("a", "i", "2026-01-01T00:00:00+00:00")],
                     [sess(alg="b"), sess(alg="a", inst="n5-seed2", ts="2026-01-04T00:00:00+00:00")])
        self.assertEqual(len(call("filterItems", items, "did not finish every place", "all")), 2)
        self.assertEqual(len(call("filterItems", items, "all", "a")), 2)
        self.assertEqual(len(call("filterItems", items, "crashed", "b")), 0)
        self.assertEqual(call("kindsOf", items), ["all", "crashed", "did not finish every place"])

    def test_group_by_version_without_duplicates(self):
        s1 = sess(file="sessions/x.json", commit="abc")
        groups = call("groupSessionsByVersion", [s1, s1, sess(file="sessions/y.json", inst="n5-seed2", commit="abc")])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["sessions"]), 2)
        self.assertEqual(groups[0]["commit"], "abc")
        self.assertEqual(groups[0]["key"], "a\u0000abc")

    def test_group_without_commit_is_unrecorded(self):
        g = call("groupSessionsByVersion", [sess(file="sessions/x.json")])
        self.assertEqual((g[0]["commit"], g[0]["key"]), (None, "a\u0000"))

    def test_compare_uses_only_examples_both_finished(self):
        def fin(inst, m, dist, days):
            return sess(inst=inst, outcome="finished", minutes=m, days=days, dist=dist)
        a = [fin("n5-seed1", 60, 10, 1), fin("n5-seed2", 120, 20, 2), sess(inst="n5-seed3")]
        b = [fin("n5-seed1", 120, 14, 2), sess(inst="n5-seed2"), fin("n5-seed3", 30, 1, 1)]
        c = call("compareFull", a, b)
        self.assertEqual(c["shared"], 3)
        self.assertEqual((c["finishedA"], c["finishedB"]), (2, 2))
        self.assertEqual(c["both"], 1)
        self.assertEqual((c["hours"]["a"], c["hours"]["b"]), (1.0, 2.0))
        self.assertEqual((c["days"]["a"], c["days"]["b"]), (1, 2))
        self.assertEqual((c["distanceKm"]["a"], c["distanceKm"]["b"]), (10, 14))

    def test_compare_with_no_common_finish_has_no_means(self):
        c = call("compareFull", [sess(inst="i")], [sess(inst="i")])
        self.assertEqual(c["both"], 0)
        self.assertIsNone(c["hours"]["a"])


if __name__ == "__main__":
    unittest.main()
