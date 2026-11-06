"""Aggregator: a pure function over run records, checked against hand-worked values."""
import unittest

from harness.aggregate import aggregate


def rec(alg, inst, n, visited, dist=10.0, minutes=100.0, runtime=10.0, valid=True,
        status="HEURISTIC", stats=None):
    return {"algorithmId": alg, "instanceId": inst, "numCustomers": n, "valid": valid,
            "status": status, "visited": visited if valid else None,
            "distanceKm": dist if valid else None, "totalMinutes": minutes if valid else None,
            "runtimeMs": runtime, "stats": stats}


def group(result, alg, n):
    return next(g for g in result["groups"] if g["algorithmId"] == alg and g["numCustomers"] == n)


class AggregateTest(unittest.TestCase):
    def test_mean_and_sample_std_per_algorithm_and_size(self):
        recs = [rec("a", "n5-seed1", 5, 2, dist=10, minutes=60, runtime=4),
                rec("a", "n5-seed2", 5, 4, dist=20, minutes=100, runtime=6),
                rec("a", "n5-seed3", 5, 6, dist=30, minutes=140, runtime=8),
                rec("a", "n10-seed1", 10, 7)]
        res = aggregate(recs)
        g = group(res, "a", 5)
        # visited 2,4,6: mean 4, sample variance (4+0+4)/2 = 4, std 2
        self.assertEqual((g["visited"]["mean"], g["visited"]["std"]), (4, 2))
        self.assertEqual((g["distanceKm"]["mean"], g["distanceKm"]["std"]), (20, 10))
        self.assertEqual((g["totalMinutes"]["mean"], g["totalMinutes"]["std"]), (100, 40))
        self.assertEqual((g["runtimeMs"]["mean"], g["runtimeMs"]["std"]), (6, 2))
        self.assertEqual(g["runs"], 3)
        self.assertEqual(group(res, "a", 10)["visited"], {"mean": 7, "std": None, "n": 1})

    def test_failures_and_timeouts_are_counted_and_excluded_from_visit_averages(self):
        recs = [rec("a", "i1", 5, 4),
                rec("a", "i2", 5, 0, valid=False, runtime=100),
                rec("a", "i3", 5, 2, status="TIME_LIMIT", runtime=300)]
        g = group(aggregate(recs), "a", 5)
        self.assertEqual((g["runs"], g["failures"], g["timeouts"]), (3, 1, 1))
        self.assertEqual(g["visited"]["mean"], 3)       # (4 + 2) / 2, the failure is left out
        self.assertEqual(g["visited"]["n"], 2)
        self.assertEqual(g["runtimeMs"]["mean"], (10 + 100 + 300) / 3)  # runtime covers every run

    def test_relative_performance_uses_best_known_visits_per_instance(self):
        recs = [rec("a", "i1", 5, 4), rec("b", "i1", 5, 2),
                rec("a", "i2", 5, 3), rec("b", "i2", 5, 6),
                rec("c", "i2", 5, 0, valid=False)]
        res = aggregate(recs)
        # best: i1 = 4, i2 = 6.  a: (4/4 + 3/6)/2 = 0.75   b: (2/4 + 6/6)/2 = 0.75
        self.assertEqual(group(res, "a", 5)["bestKnownRatio"], {"mean": 0.75, "n": 2})
        self.assertEqual(group(res, "b", 5)["visitsBehindBest"]["mean"], 1.0)  # (2 + 0) / 2
        self.assertEqual(group(res, "c", 5)["bestKnownRatio"], {"mean": None, "n": 0})
        self.assertEqual(res["bestKnown"], [
            {"instanceId": "i1", "numCustomers": 5, "visited": 4, "achievedBy": ["a"],
             "optimalReported": False},
            {"instanceId": "i2", "numCustomers": 5, "visited": 6, "achievedBy": ["b"],
             "optimalReported": False}])

    def test_all_tied_at_zero_counts_as_ratio_one(self):
        recs = [rec("a", "i1", 5, 0), rec("b", "i1", 5, 0)]
        self.assertEqual(group(aggregate(recs), "a", 5)["bestKnownRatio"]["mean"], 1.0)

    def test_optimal_is_only_claimed_when_an_algorithm_reported_it(self):
        recs = [rec("a", "i1", 5, 4, status="OPTIMAL"), rec("b", "i1", 5, 4),
                rec("a", "i2", 5, 3), rec("b", "i2", 5, 3)]
        res = aggregate(recs)
        flags = {b["instanceId"]: b["optimalReported"] for b in res["bestKnown"]}
        self.assertEqual(flags, {"i1": True, "i2": False})
        self.assertEqual(group(res, "a", 5)["optimalReports"], 1)

    def test_optimal_report_below_best_does_not_mark_instance_optimal(self):
        recs = [rec("a", "i1", 5, 3, status="OPTIMAL"), rec("b", "i1", 5, 4)]
        self.assertFalse(aggregate(recs)["bestKnown"][0]["optimalReported"])

    def test_mean_work_uses_first_present_work_key_and_handles_missing(self):
        recs = [rec("a", "i1", 5, 1, stats={"nodesExpanded": 100, "iterations": 1}),
                rec("a", "i2", 5, 1, stats={"nodesExpanded": 300}),
                rec("a", "i3", 5, 1, stats={"customersVisited": 3}),
                rec("a", "i4", 5, 1, stats=None),
                rec("b", "i1", 5, 1, stats={"customersVisited": 3})]
        res = aggregate(recs)
        self.assertEqual(group(res, "a", 5)["work"], {"mean": 200, "n": 2, "key": "nodesExpanded"})
        self.assertEqual(group(res, "b", 5)["work"], {"mean": None, "n": 0, "key": None})
        self.assertEqual(aggregate(recs, work_keys=("iterations",))["groups"][0]["work"]["mean"], 1)

    def test_summary_lists_sizes_and_algorithms_and_empty_input_is_fine(self):
        res = aggregate([rec("b", "i", 10, 1), rec("a", "j", 5, 1)])
        self.assertEqual((res["sizes"], res["algorithms"]), ([5, 10], ["a", "b"]))
        self.assertEqual(aggregate([])["groups"], [])

    def test_ignores_experiment_tags_so_any_definition_works(self):
        r = rec("a", "i1", 5, 2)
        r["experiment"] = "something-new"
        self.assertEqual(group(aggregate([r]), "a", 5)["visited"]["mean"], 2)


if __name__ == "__main__":
    unittest.main()
