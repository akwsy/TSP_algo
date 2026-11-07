"""Run-until-every-place-is-visited: the multi-day arithmetic as pure functions."""
import unittest

from harness.session import day_working_minutes, sub_instance, total_working_minutes


def day(return_minute, starts):
    return {"returnMinute": return_minute, "schedule": [{"startMinute": s} for s in starts]}


class WorkingHoursTest(unittest.TestCase):
    def test_non_final_day_counts_until_back_at_the_depot(self):
        # 06:00 departure, home at 20:00: 14 h of travelling and waiting.
        self.assertEqual(day_working_minutes(day(1200, [500, 900]), 360, final=False), 840)

    def test_final_day_counts_only_until_the_last_place_is_served(self):
        # Last place served at 11:00 (660); the drive home (back at 13:00) is not counted: 5 h.
        self.assertEqual(day_working_minutes(day(780, [500, 660]), 360, final=True), 300)

    def test_14_hour_day_plus_5_hour_last_day_is_19_hours(self):
        days = [day(1200, [900]), day(780, [500, 660])]
        self.assertEqual(total_working_minutes(days, 360), 1140)

    def test_nights_and_idle_time_are_not_counted(self):
        # Home at 12:00 on day 1 (6 h); the rest of the day and the night are ignored.
        days = [day(720, [600]), day(720, [600]), day(600, [480])]
        self.assertEqual(total_working_minutes(days, 360), 360 + 360 + 120)

    def test_single_day_session_is_just_the_final_day(self):
        self.assertEqual(total_working_minutes([day(1000, [400, 540])], 360), 180)


class SubInstanceTest(unittest.TestCase):
    def test_depot_stays_zero_customers_renumbered_matrix_cut(self):
        inst = {"instanceId": "n3-seed1", "seed": 1, "departureMinute": 360, "deadlineMinute": 1440,
                "speedKmh": 40.0, "periodMinutes": 1080,
                "locations": [{"id": i, "name": f"p{i}", "opensAt": 360 + i} for i in range(4)],
                "distanceKm": [[10 * abs(i - j) for j in range(4)] for i in range(4)]}
        sub, ids = sub_instance(inst, [3, 1], 2)  # unvisited, given out of order
        self.assertEqual(ids, [0, 1, 3])  # original order
        self.assertEqual([(l["id"], l["name"], l["opensAt"]) for l in sub["locations"]],
                         [(0, "p0", 360), (1, "p1", 361), (2, "p3", 363)])
        self.assertEqual(sub["distanceKm"], [[0, 10, 30], [10, 0, 20], [30, 20, 0]])
        self.assertEqual((sub["seed"], sub["speedKmh"], sub["departureMinute"], sub["deadlineMinute"]),
                         (1, 40.0, 360, 1440))
        self.assertEqual(sub["instanceId"], "n3-seed1-day2")


if __name__ == "__main__":
    unittest.main()
