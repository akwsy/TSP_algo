"""aggregate_sessions: hand-worked values on small fixed inputs."""
import unittest

from harness.aggregate import aggregate_sessions


def s(alg, n, seed, minutes=None, days=1, dist=10.0, rt=100, stop=None):
    return {"algorithmId": alg, "numCustomers": n, "instanceId": f"n{n}-seed{seed}",
            "outcome": "did not finish" if stop else "finished", "stopReason": stop,
            "workingMinutes": minutes, "days": days, "totalDistanceKm": dist, "totalRuntimeMs": rt}


class AggregateSessionsTest(unittest.TestCase):
    def group(self, result, alg, n):
        return next(g for g in result["groups"] if g["algorithmId"] == alg and g["numCustomers"] == n)

    def test_means_use_finished_sessions_only_in_hours(self):
        r = aggregate_sessions([
            s("a", 5, 1, minutes=60, days=1, dist=10, rt=100),
            s("a", 5, 2, minutes=180, days=3, dist=20, rt=300),
            s("a", 5, 3, minutes=9999, days=30, dist=999, rt=9999, stop="day_limit"),
        ])
        g = self.group(r, "a", 5)
        self.assertEqual((g["instances"], g["finished"], g["stopped"]), (3, 2, 1))
        self.assertEqual(g["stopReasons"], {"day_limit": 1})
        self.assertEqual(g["workingHours"]["mean"], 2.0)
        self.assertAlmostEqual(g["workingHours"]["std"], 1.4142135623730951)  # sqrt(2)
        self.assertEqual(g["workingHours"]["n"], 2)
        self.assertEqual(g["days"]["mean"], 2.0)
        self.assertEqual(g["totalDistanceKm"]["mean"], 15.0)
        self.assertEqual(g["totalRuntimeMs"]["mean"], 200.0)
        self.assertEqual(r["instancesPerSize"], {"5": 3})

    def test_std_null_for_one_and_everything_null_for_none(self):
        r = aggregate_sessions([s("a", 5, 1, minutes=30), s("b", 5, 1, stop="crashed")])
        self.assertEqual(self.group(r, "a", 5)["workingHours"], {"mean": 0.5, "std": None, "n": 1})
        b = self.group(r, "b", 5)
        self.assertEqual(b["workingHours"], {"mean": None, "std": None, "n": 0})
        self.assertEqual(b["finished"], 0)

    def test_ranking_rule(self):
        r = aggregate_sessions([
            s("c", 5, 1, minutes=120, dist=9), s("c", 5, 2, minutes=120, dist=9),
            s("d", 5, 1, minutes=120, dist=5), s("d", 5, 2, minutes=120, dist=5),
            s("e", 5, 1, minutes=60), s("e", 5, 2, minutes=60),
            s("f", 5, 1, stop="crashed"), s("f", 5, 2, stop="crashed"),
            s("g", 5, 1, minutes=1), s("g", 5, 2, stop="no_progress"),
            s("h", 5, 1, minutes=120, dist=9), s("h", 5, 2, minutes=120, dist=9),
            s("i", 5, 1, minutes=120, dist=9), s("i", 5, 2, minutes=120, dist=9),
        ])
        entries = r["ranking"][0]["entries"]
        self.assertEqual(r["ranking"][0]["numCustomers"], 5)
        self.assertEqual([e["algorithmId"] for e in entries], ["e", "d", "c", "h", "i", "g", "f"])
        self.assertEqual([e["rank"] for e in entries], [1, 2, 3, 4, 5, 6, None])
        self.assertEqual((entries[5]["finishedAll"], entries[5]["unfinished"]), (False, 1))
        self.assertEqual(entries[0]["unfinished"], 0)
        self.assertEqual(entries[6]["unfinished"], 2)

    def test_stopped_algorithms_ordered_among_themselves_by_finished_means(self):
        r = aggregate_sessions([
            s("x", 5, 1, minutes=300), s("x", 5, 2, stop="crashed"),
            s("y", 5, 1, minutes=60), s("y", 5, 2, stop="crashed"),
        ])
        self.assertEqual([e["algorithmId"] for e in r["ranking"][0]["entries"]], ["y", "x"])

    def test_overall_order_is_average_rank_across_sizes(self):
        r = aggregate_sessions([
            s("a", 5, 1, minutes=60), s("b", 5, 1, minutes=120),
            s("a", 9, 1, minutes=240), s("b", 9, 1, minutes=120),
            s("c", 5, 1, minutes=180), s("c", 9, 1, minutes=300),
        ])
        # size 5: a1 b2 c3; size 9: b1 a2 c3 -> a 1.5, b 1.5, c 3.0 (tie broken by id)
        self.assertEqual([(o["algorithmId"], o["averageRank"]) for o in r["overall"]],
                         [("a", 1.5), ("b", 1.5), ("c", 3.0)])


if __name__ == "__main__":
    unittest.main()
