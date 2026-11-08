import copy
import unittest

from harness.validator import rank_key, validate_route

# Hand-built instance. speedKmh=60 so travel minutes == km.
# d(0,1)=30, d(0,2)=50, d(1,2)=20. Depart 360, deadline 840.
# Customer 1 window [400, 500]; customer 2 window [0, 450].
BASE = {
    "instanceId": "tiny",
    "departureMinute": 360,
    "periodMinutes": 480,
    "deadlineMinute": 840,
    "speedKmh": 60,
    "locations": [
        {"id": 0, "isDepot": True, "opensAt": 0, "closesAt": 1440},
        {"id": 1, "isDepot": False, "opensAt": 400, "closesAt": 500},
        {"id": 2, "isDepot": False, "opensAt": 0, "closesAt": 450},
    ],
    "distanceKm": [[0, 30, 50], [30, 0, 20], [50, 20, 0]],
}


def inst(**changes):
    d = copy.deepcopy(BASE)
    d.update(changes)
    return d


class ValidRouteTest(unittest.TestCase):
    def test_depot_to_depot_is_valid_with_zero_visits(self):
        r = validate_route(BASE, [0, 0])
        self.assertTrue(r["valid"])
        self.assertIsNone(r["failureReason"])
        self.assertEqual(r["visited"], 0)
        self.assertEqual(r["skipped"], [1, 2])
        self.assertEqual(r["distanceKm"], 0)
        self.assertEqual(r["totalMinutes"], 0)
        self.assertEqual(r["returnMinute"], 360)
        self.assertEqual(r["schedule"], [])

    def test_waiting_when_early(self):
        # arrive 1 at 390, wait to 400, return 430.
        r = validate_route(BASE, [0, 1, 0])
        self.assertTrue(r["valid"])
        self.assertEqual(r["visited"], 1)
        self.assertEqual(r["skipped"], [2])
        self.assertEqual(r["distanceKm"], 60)
        self.assertEqual(r["travelMinutes"], 60)
        self.assertEqual(r["waitMinutes"], 10)
        self.assertEqual(r["totalMinutes"], 70)
        self.assertEqual(r["returnMinute"], 430)
        self.assertEqual(
            r["schedule"],
            [{"id": 1, "arriveMinute": 390, "startMinute": 400, "leaveMinute": 400}],
        )

    def test_two_stops_no_waiting(self):
        # 2 at 410, 1 at 430, back at 460.
        r = validate_route(BASE, [0, 2, 1, 0])
        self.assertTrue(r["valid"])
        self.assertEqual(r["visited"], 2)
        self.assertEqual(r["skipped"], [])
        self.assertEqual(r["distanceKm"], 100)
        self.assertEqual(r["waitMinutes"], 0)
        self.assertEqual(r["totalMinutes"], 100)
        self.assertEqual(r["returnMinute"], 460)

    def test_two_stops_with_waiting(self):
        # 1 at 400 (wait 10), 2 at 420, back at 470.
        r = validate_route(BASE, [0, 1, 2, 0])
        self.assertTrue(r["valid"])
        self.assertEqual(r["distanceKm"], 100)
        self.assertEqual(r["waitMinutes"], 10)
        self.assertEqual(r["totalMinutes"], 110)
        self.assertEqual(r["returnMinute"], 470)


class BoundaryTest(unittest.TestCase):
    def test_arriving_exactly_at_close_is_ok(self):
        locs = copy.deepcopy(BASE["locations"])
        locs[2]["closesAt"] = 420
        self.assertTrue(validate_route(inst(locations=locs), [0, 1, 2, 0])["valid"])

    def test_arriving_after_close_is_late(self):
        locs = copy.deepcopy(BASE["locations"])
        locs[2]["closesAt"] = 419
        r = validate_route(inst(locations=locs), [0, 1, 2, 0])
        self.assertFalse(r["valid"])
        self.assertIn("late", r["failureReason"])

    def test_returning_exactly_at_deadline_is_ok(self):
        self.assertTrue(validate_route(inst(deadlineMinute=470), [0, 1, 2, 0])["valid"])

    def test_returning_after_deadline_fails(self):
        r = validate_route(inst(deadlineMinute=469), [0, 1, 2, 0])
        self.assertFalse(r["valid"])
        self.assertIn("deadline", r["failureReason"])


class MalformedTest(unittest.TestCase):
    def assert_invalid(self, route, word):
        r = validate_route(BASE, route)
        self.assertFalse(r["valid"])
        self.assertIn(word, r["failureReason"])
        return r

    def test_repeated_customer(self):
        self.assert_invalid([0, 1, 1, 0], "repeat")

    def test_wrong_start(self):
        self.assert_invalid([1, 2, 0], "start")

    def test_wrong_end(self):
        self.assert_invalid([0, 1, 2], "end")

    def test_unknown_id(self):
        self.assert_invalid([0, 7, 0], "unknown")

    def test_non_integer_id(self):
        self.assert_invalid([0, "1", 0], "unknown")

    def test_depot_in_middle(self):
        self.assert_invalid([0, 1, 0, 2, 0], "depot")

    def test_empty_or_non_list(self):
        self.assert_invalid([], "route")
        self.assert_invalid(None, "route")
        self.assert_invalid([0], "route")

    def test_invalid_has_no_visits_or_metrics(self):
        r = self.assert_invalid([0, 1, 1, 0], "repeat")
        self.assertIsNone(r["visited"])
        self.assertIsNone(r["distanceKm"])


class RankingTest(unittest.TestCase):
    def test_more_visits_beats_shorter_distance(self):
        two = validate_route(BASE, [0, 2, 1, 0])  # 2 visits, 100 km
        one = validate_route(BASE, [0, 1, 0])  # 1 visit, 60 km
        self.assertLess(rank_key(two), rank_key(one))

    def test_equal_visits_shorter_distance_wins(self):
        a = validate_route(BASE, [0, 1, 0])  # 60 km
        b = validate_route(BASE, [0, 2, 0])  # 100 km
        self.assertEqual(a["visited"], b["visited"])
        self.assertLess(rank_key(a), rank_key(b))

    def test_failure_ranks_below_zero_visits(self):
        zero = validate_route(BASE, [0, 0])
        bad = validate_route(BASE, [0, 1, 1, 0])
        self.assertLess(rank_key(zero), rank_key(bad))

    def test_failures_tie(self):
        a = validate_route(BASE, [0, 1, 1, 0])
        b = validate_route(BASE, [0, 9, 0])
        self.assertEqual(rank_key(a), rank_key(b))


if __name__ == "__main__":
    unittest.main()
