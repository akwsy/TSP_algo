"""Full-run sessions are saved once and reused (same mechanism as the first-day runs)."""
import json
import os
import shutil
import subprocess
import sys
import unittest

from test_run import ROOT, CliCase, write_algorithm

# Visits only customer 1 per day (a 2-customer instance takes 2 days); logs the algorithm name.
ONE_PER_DAY = ('import json,os,sys\njson.load(sys.stdin)\n'
               'open(os.environ["RUN_COUNTER"],"a").write("%s\\n")\n'
               'print(json.dumps({"route":[0,1,0],"status":"HEURISTIC"}))\n')
# Same, but crashes on any later day, so its sessions stop.
CRASH_DAY2 = ('import json,os,sys\ni=json.load(sys.stdin)\n'
              'open(os.environ["RUN_COUNTER"],"a").write("%s\\n")\n'
              'if "-day" in i["instanceId"]: sys.exit(3)\n'
              'print(json.dumps({"route":[0,1,0],"status":"HEURISTIC"}))\n')


class SessionReuseTest(CliCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.algs)
        write_algorithm(self.algs, "alpha", ONE_PER_DAY % "alpha")
        write_algorithm(self.algs, "beta", ONE_PER_DAY % "beta")
        self.counter = self.tmp / "counter.txt"
        self.results = self.tmp / "results"

    def go(self, *args):
        cmd = [sys.executable, "-m", "harness.experiment", "scaling", "--sizes", "2",
               "--instances", "2", *args, "--dataset", str(self.tmp / "places.txt"),
               "--algorithms-dir", str(self.algs), "--instances-dir", str(self.tmp / "instances"),
               "--results-dir", str(self.results)]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                              env={**os.environ, "RUN_COUNTER": str(self.counter)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def executions(self):
        lines = self.counter.read_text().split() if self.counter.exists() else []
        self.counter.unlink(missing_ok=True)
        return sorted(lines)

    def sessions_index(self):
        return json.loads((self.results / "sessions-index.json").read_text())["sessions"]

    def files(self):
        return sorted(p.name for p in (self.results / "sessions").glob("*.json"))

    def test_day_one_is_not_computed_twice_and_second_run_executes_nothing(self):
        proc = self.go()
        # 2 instances x (day 1 once + day 2) per algorithm
        self.assertEqual(self.executions(), ["alpha"] * 4 + ["beta"] * 4)
        self.assertIn("Full run: reused 0 saved sessions, ran 4 new.", proc.stdout)
        self.assertIn("  alpha: reused 0, ran 2", proc.stdout)
        proc = self.go()
        self.assertEqual(self.executions(), [])
        self.assertIn("Full run: reused 4 saved sessions, ran 0 new.", proc.stdout)
        self.assertIn("  beta: reused 2, ran 0", proc.stdout)

    def test_full_aggregate_is_identical_when_every_session_is_reused(self):
        agg = self.results / "aggregates-scaling.json"
        self.go()
        first = json.loads(agg.read_text())["full"]
        self.executions()
        self.go()
        self.assertEqual(self.executions(), [])
        self.assertEqual(json.loads(agg.read_text())["full"], first)
        self.assertTrue(first)

    def test_no_duplicates_after_repeated_runs(self):
        self.go()
        files, entries = self.files(), self.sessions_index()
        self.go()
        self.assertEqual(self.files(), files)
        self.assertEqual(self.sessions_index(), entries)
        self.assertEqual(len(entries), 4)
        self.assertEqual({e["file"] for e in entries}, {f"sessions/{f}" for f in files})
        self.assertEqual(len(self.index()["runs"]), 4)  # first-day index has no session entries

    def test_editing_one_algorithm_reevaluates_only_its_sessions(self):
        self.go()
        self.executions()
        (self.algs / "beta" / "solve.py").write_text(ONE_PER_DAY % "beta" + "# edit\n")
        self.go()
        self.assertEqual(self.executions(), ["beta"] * 4)
        self.assertEqual(len(self.sessions_index()), 6)  # old version kept for history
        write_algorithm(self.algs, "gamma", ONE_PER_DAY % "gamma")
        self.go()
        self.assertEqual(self.executions(), ["gamma"] * 4)

    def test_stopped_sessions_are_reused(self):
        write_algorithm(self.algs, "crashy", CRASH_DAY2 % "crashy")
        self.go()
        stopped = [e for e in self.sessions_index() if e["algorithmId"] == "crashy"]
        self.assertEqual({e["outcome"] for e in stopped}, {"did not finish"})
        self.executions()
        proc = self.go()
        self.assertEqual(self.executions(), [])
        self.assertIn("  crashy: reused 2, ran 0", proc.stdout)

    def test_force_and_rerun_apply_to_sessions_without_stale_duplicates(self):
        self.go()
        self.executions()
        self.go("--rerun", "alpha")
        self.assertEqual(self.executions(), ["alpha"] * 4)
        self.assertEqual(len(self.files()), 4)
        self.assertEqual(len(self.sessions_index()), 4)
        self.go("--force")
        self.assertEqual(self.executions(), ["alpha"] * 4 + ["beta"] * 4)
        self.assertEqual(len(self.files()), 4)
        self.assertEqual({e["file"][len("sessions/"):] for e in self.sessions_index()}, set(self.files()))

    def test_changed_time_limit_invalidates(self):
        self.go()
        self.executions()
        meta = self.algs / "alpha" / "algorithm.json"
        meta.write_text(json.dumps({**json.loads(meta.read_text()), "timeLimitSeconds": 5}))
        self.go()
        self.assertEqual(self.executions(), ["alpha"] * 4)

    def test_changed_instance_invalidates(self):
        self.go()
        self.executions()
        places = self.tmp / "places.txt"
        places.write_text(places.read_text().replace("\t1.0\t100.0", "\t1.2\t100.0"))
        self.go()
        self.assertGreater(len(self.executions()), 0)

    def test_sessions_without_an_index_entry_are_never_reused(self):
        self.go()
        self.executions()
        (self.results / "sessions-index.json").unlink()
        self.go()
        self.assertEqual(len(self.executions()), 4)  # day 1 reused from the first-day runs
        self.assertEqual(len(self.sessions_index()), 4)
        self.assertEqual(len(self.files()), 4)  # orphans of the same session are not left behind


if __name__ == "__main__":
    unittest.main()
