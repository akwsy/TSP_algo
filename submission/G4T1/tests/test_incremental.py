"""Incremental evaluation: saved runs are reused unless the algorithm or instance changed."""
import json
import os
import shutil
import subprocess
import sys
import unittest

from test_run import ROOT, CliCase, write_algorithm

# Appends the algorithm's name to a counter file OUTSIDE the algorithm folder (editing the
# folder would change its fingerprint), then visits nobody.
COUNTING = ('import json,os,sys\njson.load(sys.stdin)\n'
            'open(os.environ["RUN_COUNTER"],"a").write("%s\\n")\n'
            'print(json.dumps({"route":[0,0],"status":"HEURISTIC"}))\n')


class IncrementalTest(CliCase):
    def setUp(self):
        super().setUp()
        shutil.rmtree(self.algs)
        for name in ("alpha", "beta"):
            write_algorithm(self.algs, name, COUNTING % name)
        self.counter = self.tmp / "counter.txt"

    def cmd(self, *args, sizes=("1", "2"), instances="2"):
        return [sys.executable, "-m", "harness.experiment", "scaling", "--sizes", *sizes,
                "--instances", instances, *args,
                "--dataset", str(self.tmp / "places.txt"), "--algorithms-dir", str(self.algs),
                "--instances-dir", str(self.tmp / "instances"), "--results-dir", str(self.tmp / "results")]

    def go(self, *args, **kw):
        proc = subprocess.run(self.cmd(*args, **kw), cwd=ROOT, capture_output=True, text=True,
                              env={**os.environ, "RUN_COUNTER": str(self.counter)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def executions(self):
        """Algorithm names executed since the last call."""
        lines = self.counter.read_text().split() if self.counter.exists() else []
        self.counter.unlink(missing_ok=True)
        return sorted(lines)

    def aggregates(self):
        return json.loads((self.tmp / "results" / "aggregates-scaling.json").read_text())

    def test_second_run_executes_nothing_and_says_so(self):
        self.go()
        self.assertEqual(len(self.executions()), 8)
        first = self.aggregates()
        proc = self.go()
        self.assertEqual(self.executions(), [])
        self.assertIn("Reusing 8 saved runs, running 0 new", proc.stdout)
        self.assertEqual(self.aggregates(), first)

    def test_index_has_no_duplicates_and_keeps_original_entries(self):
        self.go()
        before = self.index()["runs"]
        self.go()
        self.assertEqual(self.index()["runs"], before)
        self.assertEqual(len({r["file"] for r in before}), 8)
        self.assertTrue(all(r["fingerprint"] and r["instanceHash"] for r in before))
        self.assertTrue(all(r["experiment"] == "scaling" for r in before))

    def test_editing_one_algorithm_reruns_only_it(self):
        self.go()
        self.executions()
        (self.algs / "beta" / "solve.py").write_text(COUNTING % "beta" + "# edit\n")
        self.go()
        self.assertEqual(self.executions(), ["beta"] * 4)

    def test_changing_the_time_limit_reruns_that_algorithm(self):
        self.go()
        self.executions()
        meta = self.algs / "alpha" / "algorithm.json"
        meta.write_text(json.dumps({**json.loads(meta.read_text()), "timeLimitSeconds": 5}))
        self.go()
        self.assertEqual(self.executions(), ["alpha"] * 4)

    def test_adding_an_algorithm_runs_only_it(self):
        self.go()
        self.executions()
        write_algorithm(self.algs, "gamma", COUNTING % "gamma")
        self.go()
        self.assertEqual(self.executions(), ["gamma"] * 4)
        self.assertEqual(self.aggregates()["algorithms"], ["alpha", "beta", "gamma"])

    def test_removed_algorithm_leaves_the_aggregates(self):
        self.go()
        self.executions()
        shutil.rmtree(self.algs / "beta")
        proc = self.go()
        self.assertEqual(self.executions(), [])
        self.assertEqual(self.aggregates()["algorithms"], ["alpha"])
        self.assertIn("Reusing 4 saved runs, running 0 new", proc.stdout)

    def test_force_reruns_everything(self):
        self.go()
        self.executions()
        self.go("--force")
        self.assertEqual(self.executions(), ["alpha"] * 4 + ["beta"] * 4)

    def test_forced_rerun_supersedes_index_entries_of_identical_code(self):
        self.go()
        old = {r["file"] for r in self.index()["runs"]}
        self.go("--force")
        runs = self.index()["runs"]
        self.assertEqual(len(runs), 8)
        self.assertFalse(old & {r["file"] for r in runs})

    def test_edited_algorithm_keeps_its_old_version_in_the_index_for_history(self):
        self.go()
        (self.algs / "beta" / "solve.py").write_text(COUNTING % "beta" + "# edit\n")
        self.go()
        self.assertEqual(len(self.index()["runs"]), 12)

    def test_rerun_reruns_only_the_named_algorithm(self):
        self.go()
        self.executions()
        self.go("--rerun", "alpha")
        self.assertEqual(self.executions(), ["alpha"] * 4)

    def test_rerun_unknown_algorithm_is_an_error(self):
        proc = subprocess.run(self.cmd("--rerun", "nope"), cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("no such algorithm", proc.stderr)

    def test_changed_dataset_reruns_the_changed_instances(self):
        self.go(sizes=("2",))
        self.executions()
        places = self.tmp / "places.txt"
        places.write_text(places.read_text().replace("\t1.0\t100.0", "\t1.2\t100.0"))
        self.go(sizes=("2",))
        self.assertEqual(self.executions(), ["alpha"] * 2 + ["beta"] * 2)

    def test_extending_sizes_runs_only_missing_pairs(self):
        self.go(sizes=("1",))
        self.executions()
        self.go(sizes=("1", "2"))
        self.assertEqual(self.executions(), ["alpha"] * 2 + ["beta"] * 2)
        self.assertEqual(self.aggregates()["sizes"], [1, 2])

    def test_shrinking_the_experiment_aggregates_only_current_instances(self):
        self.go()
        self.executions()
        self.go(sizes=("1",))
        self.assertEqual(self.executions(), [])
        self.assertEqual(self.aggregates()["sizes"], [1])
        self.assertTrue(all(g["numCustomers"] == 1 for g in self.aggregates()["groups"]))

    def test_old_records_without_fingerprints_run_once(self):
        self.go()
        self.executions()
        path = self.tmp / "results" / "index.json"
        idx = json.loads(path.read_text())
        for r in idx["runs"]:
            del r["fingerprint"], r["instanceHash"]
        path.write_text(json.dumps(idx))
        proc = self.go()
        self.assertEqual(len(self.executions()), 8)
        self.assertIn("no fingerprint", proc.stdout)
        self.go()
        self.assertEqual(self.executions(), [])


if __name__ == "__main__":
    unittest.main()
