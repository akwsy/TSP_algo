"""Sessions that cannot finish: each stop condition, end to end through the experiment command."""
import json
import os
import shutil
import subprocess
import sys

from test_run import ROOT, CliCase, write_algorithm

LATER = ROOT / "tests" / "fixtures" / "broken" / "later_day.py"
ONE_PER_DAY = ('import json,sys\njson.load(sys.stdin)\n'
               'print(json.dumps({"route":[0,1,0],"status":"HEURISTIC"}))\n')
BAD_FIRST = 'import sys\nprint("{not json")\n'


class StopTest(CliCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.algs)

    def add(self, mode, limit=1):
        folder = self.algs / mode
        folder.mkdir(parents=True)
        (folder / "algorithm.json").write_text(json.dumps({
            "id": mode, "displayName": mode, "timeLimitSeconds": limit,
            "command": [sys.executable, str(LATER), mode]}))

    def session(self, alg, env=None, instances="1"):
        cmd = [sys.executable, "-m", "harness.experiment", "scaling", "--sizes", "2",
               "--instances", instances, "--dataset", str(self.tmp / "places.txt"),
               "--algorithms-dir", str(self.algs), "--instances-dir", str(self.tmp / "instances"),
               "--results-dir", str(self.tmp / "results")]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env={**os.environ, **(env or {})})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        files = sorted((self.tmp / "results" / "sessions").glob(f"{alg}__n2-seed1__*.json"))
        return json.loads(files[-1].read_text())

    def assertStopped(self, s, reason, day, text):
        self.assertEqual((s["outcome"], s["stopReason"], s["stopDay"]), ("did not finish", reason, day))
        self.assertEqual(s["explanation"], text)
        self.assertTrue(s["partialFigures"])
        self.assertEqual(s["visitedSoFar"], 1)
        self.assertEqual(s["unvisitedAtStop"], 1)
        # Working time so far = day 1's whole day (to its return to the depot); not a finishing time.
        day1 = s["dayRecords"][0]
        self.assertAlmostEqual(s["workingMinutes"], day1["returnMinute"] - 360)
        self.assertGreater(s["workingMinutes"], 0)
        self.assertEqual(s["days"], len(s["dayRecords"]))

    def test_crash_on_day_2(self):
        self.add("crash")
        s = self.session("crash")
        self.assertStopped(s, "crashed", 2, "Stopped on day 2: the algorithm crashed (exited with code 3)")
        self.assertIsNone(s["dayRecords"][1]["workingMinutes"])

    def test_invalid_route_on_day_2(self):
        self.add("invalid-route")
        self.assertStopped(self.session("invalid-route"), "invalid_route", 2,
                           "Stopped on day 2: the algorithm gave an invalid route (route repeats a customer)")

    def test_unreadable_output_on_day_2(self):
        self.add("unreadable")
        self.assertStopped(self.session("unreadable"), "unreadable_output", 2,
                           "Stopped on day 2: the algorithm's output could not be read (output is not valid JSON)")

    def test_timeout_with_no_answer_on_day_2(self):
        self.add("no-answer-then-sleep")
        self.assertStopped(self.session("no-answer-then-sleep"), "timed_out", 2,
                           "Stopped on day 2: the algorithm ran out of time (exceeded the time limit of 1 s "
                           "and was killed) and gave no usable answer")

    def test_visiting_nothing_on_day_2(self):
        self.add("visit-nothing")
        self.assertStopped(self.session("visit-nothing"), "no_progress", 2,
                           "Stopped on day 2: the algorithm visited no new places (1 still unvisited)")

    def test_timeout_that_printed_a_valid_route_still_counts_as_progress(self):
        self.add("valid-then-sleep")
        s = self.session("valid-then-sleep")
        self.assertEqual((s["outcome"], s["days"], s["visitedSoFar"]), ("finished", 2, 2))
        self.assertTrue(s["dayRecords"][1]["killed"])

    def test_command_that_cannot_start_stops_on_day_1(self):
        folder = self.algs / "nobin"
        folder.mkdir(parents=True)
        (folder / "algorithm.json").write_text(json.dumps({
            "id": "nobin", "displayName": "nobin", "command": ["/nonexistent/no-such-binary"]}))
        s = self.session("nobin")
        self.assertEqual((s["outcome"], s["stopReason"], s["stopDay"]), ("did not finish", "could_not_start", 1))
        self.assertTrue(s["explanation"].startswith("Stopped on day 1: the algorithm could not be started ("))
        self.assertEqual((s["visitedSoFar"], s["workingMinutes"]), (0, 0))

    def test_failure_on_day_1_is_reported_too(self):
        write_algorithm(self.algs, "bad-first", BAD_FIRST)
        s = self.session("bad-first")
        self.assertEqual((s["stopReason"], s["stopDay"], s["visitedSoFar"]), ("unreadable_output", 1, 0))

    def test_day_limit_stops_with_places_remaining(self):
        write_algorithm(self.algs, "slow", ONE_PER_DAY)
        # Test hook: TSP_MAX_DAYS shrinks the cap so no 30 slow runs are needed
        # (the real default of 30 is asserted in test_session_constants).
        s = self.session("slow", env={"TSP_MAX_DAYS": "1"})
        self.assertEqual((s["outcome"], s["stopReason"], s["stopDay"], s["days"]), ("did not finish", "day_limit", 1, 1))
        self.assertEqual(s["explanation"], "Stopped after day 1: 1 place still unvisited (day limit reached)")
        self.assertEqual((s["visitedSoFar"], s["unvisitedAtStop"], s["partialFigures"]), (1, 1, True))

    def test_default_day_limit_is_30(self):
        sys.path.insert(0, str(ROOT))
        from harness import session
        self.assertEqual(session.MAX_DAYS, 30)

    def test_finished_session_has_no_partial_figures(self):
        write_algorithm(self.algs, "slow", ONE_PER_DAY)
        s = self.session("slow")
        self.assertEqual((s["outcome"], s["partialFigures"], s["unvisitedAtStop"]), ("finished", False, 0))
