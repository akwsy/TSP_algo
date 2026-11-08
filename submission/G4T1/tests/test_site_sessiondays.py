"""Full-run day logic (site/js/lib/sessiondays.js), run under node. Expected values are hand-worked."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

MODEL = Path(__file__).resolve().parent.parent / "site" / "js" / "lib" / "sessiondays.js"


def call(fn, *args):
    script = (f"import * as m from {json.dumps(MODEL.as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def day(n, visited, valid=True, ret=600):
    route = [0, *visited, 0] if valid else None
    sched = [{"id": v, "arriveMinute": 400 + i * 10, "startMinute": 420 + i * 10, "leaveMinute": 425 + i * 10}
             for i, v in enumerate(visited)] if valid else None
    return {"day": n, "route": route, "schedule": sched, "visited": visited if valid else [], "valid": valid,
            "returnMinute": ret, "distanceKm": 12.0 * len(visited), "workingMinutes": 240 if visited else None}


INST = {"departureMinute": 360, "deadlineMinute": 1440,
        "locations": [{"id": i, "name": f"P{i}", "isDepot": i == 0} for i in range(6)]}
FINISHED = {"outcome": "finished", "days": 3, "numCustomers": 5, "workingMinutes": 450, "totalDistanceKm": 60.0,
            "algorithmId": "a", "dayRecords": [day(1, [2, 4]), day(2, [1]), day(3, [3, 5])]}
STOPPED = {"outcome": "did not finish", "days": 3, "numCustomers": 5, "stopDay": 3, "stopReason": "no_progress",
           "explanation": "Stopped on day 3: the algorithm visited no new places (2 still unvisited)",
           "visitedSoFar": 3, "workingMinutes": 180, "totalDistanceKm": 36.0, "unvisitedAtStop": 2,
           "algorithmId": "b", "dayRecords": [day(1, [2, 4]), day(2, [1]), day(3, [], ret=None)]}
CRASHED = {**STOPPED, "days": 1, "stopDay": 1, "explanation": "Stopped on day 1: the algorithm crashed (exited with code 3)",
           "dayRecords": [day(1, [], valid=False)], "visitedSoFar": 0}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SessionDaysTest(unittest.TestCase):
    def test_day_options_are_exactly_the_completed_days(self):
        self.assertEqual(call("dayCount", FINISHED), 3)
        self.assertEqual(call("dayCount", STOPPED), 2)  # the day that visited nothing was not completed
        self.assertEqual(call("dayCount", CRASHED), 0)
        self.assertEqual(call("dayOptions", 2), [{"value": 1, "label": "Day 1"}, {"value": 2, "label": "Day 2"}])
        self.assertEqual(call("maxDays", [FINISHED, STOPPED]), 3)
        self.assertEqual(call("clampDay", 9, 3), 3)
        self.assertEqual(call("clampDay", "x", 3), 1)

    def test_earlier_days_are_done_and_the_rest_still_to_visit(self):
        self.assertEqual(call("doneBefore", FINISHED, 1), [])
        self.assertEqual(call("doneBefore", FINISHED, 3), [1, 2, 4])
        self.assertEqual(call("stillToVisit", INST, FINISHED, 1), [1, 2, 3, 4, 5])
        self.assertEqual(call("stillToVisit", INST, FINISHED, 3), [3, 5])

    def test_day_run_is_map_input_in_original_ids(self):
        r = call("dayRun", INST, FINISHED, 3)
        self.assertEqual(r["route"], [0, 3, 5, 0])
        self.assertEqual(r["visited"], 2)
        self.assertEqual(r["schedule"][0]["id"], 3)
        self.assertEqual(r["returnMinute"], 600)
        self.assertEqual(r["totalMinutes"], 240)  # back at 10:00 after leaving at 06:00
        self.assertEqual(call("dayRun", INST, FINISHED, 4), None)

    def test_a_day_the_session_does_not_have_says_why(self):
        self.assertEqual(call("dayEnding", FINISHED, 2), None)
        self.assertEqual(call("dayEnding", FINISHED, 4), "finished on day 3")
        self.assertEqual(call("dayEnding", STOPPED, 3), "stopped after day 2, did not finish")
        self.assertEqual(call("dayEnding", CRASHED, 1), "stopped before finishing a day, did not finish")

    def test_summary_of_finished_and_stopped_sessions(self):
        s = call("sessionSummary", FINISHED)
        self.assertEqual(s["finished"], True)
        self.assertEqual(s["rows"], [["Working time", "7.5 hours"], ["Days", "3"], ["Distance", "60 km"]])
        t = call("sessionSummary", STOPPED)
        self.assertEqual(t["finished"], False)
        self.assertEqual(t["explanation"], STOPPED["explanation"])
        self.assertEqual(t["rows"], [["Days completed", "2"], ["Places visited so far", "3 of 5"],
                                     ["Working time so far", "3 hours"], ["Distance so far", "36 km"]])
        self.assertEqual(t["note"], "so far, not a finishing time")

    def test_picking_sessions_for_a_problem(self):
        idx = [{"instanceId": "n10-seed4", "algorithmId": "b", "numCustomers": 10, "seed": 4, "timestamp": "1", "file": "x"},
               {"instanceId": "n10-seed4", "algorithmId": "b", "numCustomers": 10, "seed": 4, "timestamp": "2", "file": "y"},
               {"instanceId": "n10-seed4", "algorithmId": "a", "numCustomers": 10, "seed": 4, "timestamp": "1", "file": "z"},
               {"instanceId": "n5-seed2", "algorithmId": "a", "numCustomers": 5, "seed": 2, "timestamp": "1", "file": "w"}]
        self.assertEqual([e["file"] for e in call("latestPerAlgorithm", idx, "n10-seed4")], ["z", "y"])
        self.assertEqual(call("sessionInstanceIds", idx), ["n5-seed2", "n10-seed4"])


if __name__ == "__main__":
    unittest.main()
