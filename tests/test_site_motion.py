"""Motion logic (site/js/lib/motion.js), run under node: the route draw-in schedule, count-up values, the reduced-motion
switch and the theme choice. Expected values are hand-worked."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

MOTION = Path(__file__).resolve().parent.parent / "site" / "js" / "lib" / "motion.js"


def call(fn, *args):
    script = f"import * as m from {json.dumps(MOTION.as_uri())};console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));"
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class RevealScheduleTest(unittest.TestCase):
    def test_legs_draw_one_after_another_in_visiting_order(self):
        # 4 legs, 2000 ms budget, legs capped at 400 ms: each leg gets 400 ms, back to back.
        s = call("revealSchedule", 4, {"budgetMs": 2000, "maxLegMs": 400})
        self.assertEqual(s, [{"start": 0, "duration": 400}, {"start": 400, "duration": 400},
                             {"start": 800, "duration": 400}, {"start": 1200, "duration": 400}])

    def test_long_routes_are_squeezed_into_the_budget(self):
        # 20 legs in 3000 ms: 150 ms each, the last one ends exactly at 3000.
        s = call("revealSchedule", 20, {"budgetMs": 3000, "maxLegMs": 400, "minLegMs": 40})
        self.assertEqual(len(s), 20)
        self.assertEqual(s[0], {"start": 0, "duration": 150})
        self.assertEqual(s[-1]["start"] + s[-1]["duration"], 3000)

    def test_very_long_routes_keep_a_minimum_leg_time_and_overlap_instead_of_overrunning(self):
        # 200 legs, 40 ms minimum: legs overlap so the whole draw still ends at the 3000 ms budget.
        s = call("revealSchedule", 200, {"budgetMs": 3000, "maxLegMs": 400, "minLegMs": 40})
        self.assertTrue(all(x["duration"] == 40 for x in s))
        self.assertEqual(s[-1]["start"] + s[-1]["duration"], 3000)
        starts = [x["start"] for x in s]
        self.assertEqual(starts, sorted(starts))

    def test_no_legs_gives_an_empty_schedule(self):
        self.assertEqual(call("revealSchedule", 0, {"budgetMs": 3000}), [])


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CountUpTest(unittest.TestCase):
    def test_starts_at_zero_and_ends_exactly_on_the_target(self):
        self.assertEqual(call("countUpValue", 7.25, 0), 0)
        self.assertEqual(call("countUpValue", 7.25, 1), 7.25)

    def test_eases_out_so_most_of_the_climb_happens_early(self):
        # ease-out cubic: 1 - (1 - 0.5)^3 = 0.875
        self.assertAlmostEqual(call("countUpValue", 8, 0.5), 7.0)

    def test_progress_outside_zero_to_one_is_clamped(self):
        self.assertEqual(call("countUpValue", 3, 1.7), 3)
        self.assertEqual(call("countUpValue", 3, -1), 0)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class MotionSwitchTest(unittest.TestCase):
    def test_full_motion_only_when_neither_the_system_nor_the_visitor_asks_to_reduce(self):
        self.assertTrue(call("motionAllowed", False, None))
        self.assertTrue(call("motionAllowed", False, "full"))
        self.assertFalse(call("motionAllowed", False, "reduce"))

    def test_the_system_setting_always_wins_over_a_stored_choice(self):
        self.assertFalse(call("motionAllowed", True, None))
        self.assertFalse(call("motionAllowed", True, "full"))

    def test_stagger_delay_grows_per_row_but_is_capped(self):
        self.assertEqual(call("staggerDelay", 0, 40, 400), 0)
        self.assertEqual(call("staggerDelay", 3, 40, 400), 120)
        self.assertEqual(call("staggerDelay", 50, 40, 400), 400)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ThemeChoiceTest(unittest.TestCase):
    def test_dark_is_the_default_when_nothing_valid_is_stored(self):
        self.assertEqual(call("resolveTheme", None), "dark")
        self.assertEqual(call("resolveTheme", "purple"), "dark")
        self.assertEqual(call("resolveTheme", "light"), "light")
        self.assertEqual(call("resolveTheme", "system"), "system")

    def test_the_theme_button_cycles_dark_light_system(self):
        self.assertEqual(call("nextTheme", "dark"), "light")
        self.assertEqual(call("nextTheme", "light"), "system")
        self.assertEqual(call("nextTheme", "system"), "dark")


if __name__ == "__main__":
    unittest.main()
