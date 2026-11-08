"""Paired comparisons and sweep grouping: pure functions, hand-worked values."""
import unittest

from harness.aggregate import aggregate, pairwise


def rec(alg, inst, route, dist=10.0, value=10, param="speed", valid=True, n=30):
    return {"algorithmId": alg, "instanceId": inst, "numCustomers": n, "valid": valid,
            "status": "HEURISTIC", "visited": len(route) - 2 if valid else None,
            "distanceKm": dist if valid else None, "totalMinutes": 5.0 if valid else None,
            "runtimeMs": 1.0, "stats": None, "killed": False,
            "route": route if valid else None, "sweepParam": param, "sweepValue": value}


def routes(*ids):
    return [0, *ids, 0]


# One sweep value, two algorithms, five instances (hand-worked in the tests below).
A = [rec("a", "i1", routes(1, 2, 3), dist=10), rec("a", "i2", routes(1, 2, 3, 4, 5)),
     rec("a", "i3", routes(1, 2)), rec("a", "i4", routes(1)),
     rec("a", "i5", routes(), valid=False)]
B = [rec("b", "i1", routes(2, 3, 1), dist=12), rec("b", "i2", routes(1, 2, 3, 4)),
     rec("b", "i3", routes(2, 3)), rec("b", "i4", routes(1, 2, 3, 4)),
     rec("b", "i5", routes(1, 2, 3))]


class PairwiseTest(unittest.TestCase):
    def one(self, recs):
        pairs = pairwise(recs)
        self.assertEqual(len(pairs), 1)
        return pairs[0]

    def test_wins_ties_exclusions_and_means(self):
        p = self.one(A + B)
        self.assertEqual((p["sweepParam"], p["sweepValue"], p["a"], p["b"]), ("speed", 10, "a", "b"))
        # i1 equal visits, a shorter by 2 km: a wins. i2 5 v 4: a. i3 2 v 2, equal distance: tie.
        # i4 1 v 4: b. i5 a invalid: excluded.
        self.assertEqual((p["instances"], p["excluded"]), (4, 1))
        self.assertEqual((p["aWins"], p["bWins"], p["ties"]), (2, 1, 1))
        self.assertEqual(p["meanVisitDiff"], -0.5)                # (0 + 1 + 0 - 3) / 4
        self.assertEqual(p["meanDistanceDiffWhenEqualVisits"], -1.0)  # i1: -2, i3: 0
        # Jaccard: i1 3/3, i2 4/5, i3 1/3, i4 1/4
        self.assertAlmostEqual(p["meanOverlap"], (1 + 0.8 + 1 / 3 + 0.25) / 4)

    def test_largest_gaps_sorted_by_gap_then_instance_and_skip_zero_gaps(self):
        p = self.one(A + B)
        self.assertEqual(p["largestGaps"], [
            {"instanceId": "i4", "aVisited": 1, "bVisited": 4, "difference": -3},
            {"instanceId": "i2", "aVisited": 5, "bVisited": 4, "difference": 1}])

    def test_largest_gaps_keeps_five_largest(self):
        a = [rec("a", f"i{k}", routes(*range(1, k + 2))) for k in range(1, 8)]
        b = [rec("b", f"i{k}", routes()) for k in range(1, 8)]
        gaps = self.one(a + b)["largestGaps"]
        self.assertEqual([g["instanceId"] for g in gaps], ["i7", "i6", "i5", "i4", "i3"])

    def test_gap_ties_sort_by_instance_id(self):
        a = [rec("a", "z", routes(1)), rec("a", "m", routes(1))]
        b = [rec("b", "z", routes()), rec("b", "m", routes())]
        self.assertEqual([g["instanceId"] for g in self.one(a + b)["largestGaps"]], ["m", "z"])

    def test_distance_difference_within_1e9_is_a_tie(self):
        a = [rec("a", "i1", routes(1), dist=10.0)]
        b = [rec("b", "i1", routes(1), dist=10.0 + 1e-10)]
        p = self.one(a + b)
        self.assertEqual((p["aWins"], p["bWins"], p["ties"]), (0, 0, 1))

    def test_ci_is_deterministic_inside_the_data_range_and_exact_for_constant_diffs(self):
        p1, p2 = self.one(A + B), self.one(list(reversed(A + B)))
        self.assertEqual(p1["visitDiffCI95"], p2["visitDiffCI95"])
        low, high = p1["visitDiffCI95"]
        self.assertTrue(-3 <= low <= -0.5 <= high <= 1, (low, high))
        a = [rec("a", f"i{k}", routes(1, 2, 3)) for k in range(3)]
        b = [rec("b", f"i{k}", routes(1)) for k in range(3)]
        self.assertEqual(self.one(a + b)["visitDiffCI95"], [2.0, 2.0])

    def test_ci_for_two_diffs_spans_both(self):
        a = [rec("a", "i1", routes(1, 2)), rec("a", "i2", routes())]
        b = [rec("b", "i1", routes()), rec("b", "i2", routes())]
        # diffs 2 and 0: resampled means are 0, 1 or 2, and with 2000 resamples both ends occur.
        self.assertEqual(self.one(a + b)["visitDiffCI95"], [0.0, 2.0])

    def test_both_empty_routes_overlap_is_one_and_no_valid_pair_gives_nulls(self):
        p = self.one([rec("a", "i1", routes()), rec("b", "i1", routes())])
        self.assertEqual((p["meanOverlap"], p["ties"], p["largestGaps"]), (1.0, 1, []))
        q = self.one([rec("a", "i1", routes(), valid=False), rec("b", "i1", routes(1))])
        self.assertEqual((q["instances"], q["excluded"], q["meanVisitDiff"], q["visitDiffCI95"],
                          q["meanDistanceDiffWhenEqualVisits"], q["meanOverlap"]),
                         (0, 1, None, None, None, None))

    def test_pairs_per_sweep_value_in_sorted_order_a_before_b(self):
        recs = [rec(alg, "i1", routes(1), value=v) for v in (20, 10) for alg in ("c", "a", "b")]
        got = [(p["sweepValue"], p["a"], p["b"]) for p in pairwise(recs)]
        self.assertEqual(got, [(10, "a", "b"), (10, "a", "c"), (10, "b", "c"),
                               (20, "a", "b"), (20, "a", "c"), (20, "b", "c")])


class SweepGroupingTest(unittest.TestCase):
    def test_groups_by_sweep_value_and_carry_it_with_num_customers(self):
        recs = [rec("a", "i1", routes(1), value=10), rec("a", "i2", routes(1, 2), value=20),
                rec("a", "i3", routes(1, 2, 3, 4), value=20)]
        res = aggregate(recs)
        self.assertEqual(res["sweepValues"], [10, 20])
        g10, g20 = res["groups"]
        self.assertEqual((g10["sweepParam"], g10["sweepValue"], g10["numCustomers"], g10["runs"]),
                         ("speed", 10, 30, 1))
        self.assertEqual((g20["sweepValue"], g20["visited"]["mean"]), (20, 3))

    def test_records_without_sweep_fields_fall_back_to_customers(self):
        r = rec("a", "i1", routes(1), n=5)
        del r["sweepParam"], r["sweepValue"]
        res = aggregate([r])
        self.assertEqual((res["groups"][0]["sweepParam"], res["groups"][0]["sweepValue"],
                          res["sweepValues"]), ("customers", 5, [5]))


if __name__ == "__main__":
    unittest.main()
