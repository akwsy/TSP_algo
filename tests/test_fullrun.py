"""'Until every place is visited': the experiment command end to end on the tiny fixture dataset."""
import json
import os
import shutil
import subprocess
import sys

from test_run import ROOT, CliCase, write_algorithm

# Visits only customer 1 each day (so a 2-customer instance needs 2 days) and logs every input
# it receives to a file OUTSIDE the algorithm folder.
ONE_PER_DAY = ('import json,os,sys\ni=json.load(sys.stdin)\n'
               'open(os.environ["RUN_LOG"],"a").write(json.dumps(i)+"\\n")\n'
               'print(json.dumps({"route":[0,1,0],"status":"HEURISTIC"}))\n')
# Visits every customer it can reach in order 1,2 if that is valid, else only customer 1.
NOBODY = 'import json,sys\njson.load(sys.stdin)\nprint(json.dumps({"route":[0,0],"status":"HEURISTIC"}))\n'


class FullRunTest(CliCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.algs)
        write_algorithm(self.algs, "one-per-day", ONE_PER_DAY)
        self.log = self.tmp / "log.jsonl"

    def go(self, *args, sizes=("2",), instances="2"):
        cmd = [sys.executable, "-m", "harness.experiment", "scaling", "--sizes", *sizes,
               "--instances", instances, *args,
               "--dataset", str(self.tmp / "places.txt"), "--algorithms-dir", str(self.algs),
               "--instances-dir", str(self.tmp / "instances"), "--results-dir", str(self.tmp / "results")]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              env={**os.environ, "RUN_LOG": str(self.log)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def sessions(self):
        files = sorted((self.tmp / "results" / "sessions").glob("*.json"))
        return [json.loads(f.read_text()) for f in files]

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def test_one_session_per_algorithm_and_instance_beside_the_one_day_results(self):
        self.go()
        sessions = self.sessions()
        self.assertEqual(sorted(s["instanceId"] for s in sessions), ["n2-seed1", "n2-seed2"])
        self.assertEqual({s["algorithmId"] for s in sessions}, {"one-per-day"})
        self.assertEqual(len(self.index()["runs"]), 2)  # the one-day index is unchanged
        self.assertTrue((self.tmp / "results" / "aggregates-scaling.json").exists())

    def test_option_limits_how_many_instances_get_a_session(self):
        self.go("--full-run-instances", "1")
        self.assertEqual([s["instanceId"] for s in self.sessions()], ["n2-seed1"])
        shutil.rmtree(self.tmp / "results")
        self.go("--full-run-instances", "0")
        self.assertEqual(self.sessions() if (self.tmp / "results" / "sessions").exists() else [], [])

    def test_two_days_when_one_place_is_visited_per_day(self):
        self.go()
        s = next(s for s in self.sessions() if s["instanceId"] == "n2-seed1")
        self.assertEqual((s["outcome"], s["days"], s["visitedSoFar"]), ("finished", 2, 2))
        d1, d2 = s["dayRecords"]
        self.assertEqual((d1["route"], d1["visited"], d2["route"], d2["visited"]),
                         ([0, 1, 0], [1], [0, 2, 0], [2]))
        self.assertEqual([x["schedule"][0]["id"] for x in (d1, d2)], [1, 2])
        # Day 1 is the ordinary first-day run.
        one_day = self.record(self.entry("one-per-day", 1))
        self.assertEqual((d1["route"], d1["returnMinute"], d1["distanceKm"]),
                         (one_day["route"], one_day["returnMinute"], one_day["distanceKm"]))

    def test_working_hours_follow_the_definition(self):
        self.go()
        s = next(s for s in self.sessions() if s["instanceId"] == "n2-seed1")
        inst = json.loads((self.tmp / "instances" / "n2-seed1.json").read_text())
        d, opens = inst["distanceKm"], [l["opensAt"] for l in inst["locations"]]
        leg = lambda a, b: d[a][b] / 40 * 60  # minutes at 40 km/h
        serve1 = max(360 + leg(0, 1), opens[1])
        serve2 = max(360 + leg(0, 2), opens[2])
        home1 = serve1 + leg(1, 0)
        self.assertAlmostEqual(s["dayRecords"][0]["workingMinutes"], home1 - 360)   # whole day 1
        self.assertAlmostEqual(s["dayRecords"][1]["workingMinutes"], serve2 - 360)  # day 2: until served
        self.assertAlmostEqual(s["workingMinutes"], (home1 - 360) + (serve2 - 360))
        self.assertAlmostEqual(s["totalDistanceKm"], 2 * d[0][1] + 2 * d[0][2])
        self.assertAlmostEqual(s["finalReturnMinute"], serve2 + leg(2, 0))
        self.assertAlmostEqual(s["totalRuntimeMs"], sum(x["runtimeMs"] for x in s["dayRecords"]))

    def test_later_day_receives_only_unvisited_places_with_depot_zero(self):
        self.go(instances="1")
        inst = json.loads((self.tmp / "instances" / "n2-seed1.json").read_text())
        first, second = self.calls()  # day 1 (full instance), day 2
        self.assertEqual(len(first["locations"]), 3)
        self.assertEqual([l["id"] for l in second["locations"]], [0, 1])
        self.assertEqual(second["locations"][1]["name"], inst["locations"][2]["name"])
        self.assertEqual(second["distanceKm"],
                         [[0, inst["distanceKm"][0][2]], [inst["distanceKm"][2][0], 0]])
        for key in ("seed", "speedKmh", "departureMinute", "deadlineMinute"):
            self.assertEqual(second[key], inst[key])
        self.assertEqual(second["locations"][1]["opensAt"], inst["locations"][2]["opensAt"])

    def test_day_one_reuses_the_first_day_run_without_calling_again(self):
        self.go(instances="1")
        self.assertEqual(len(self.calls()), 2)  # one day-1 call (shared) + one day-2 call

    def test_a_stuck_algorithm_cannot_loop_forever(self):
        write_algorithm(self.algs, "nobody", NOBODY)
        self.go()
        s = next(s for s in self.sessions() if s["algorithmId"] == "nobody")
        self.assertEqual((s["outcome"], s["stopReason"], s["stopDay"], s["days"]),
                         ("did not finish", "no_progress", 1, 1))
        self.assertIn("day 1", s["explanation"])
