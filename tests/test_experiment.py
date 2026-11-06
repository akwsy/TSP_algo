"""Experiment command, tested end to end with the tiny fixture dataset."""
import json
import subprocess
import sys
import unittest

from harness.experiments import EXPERIMENTS
from test_run import ROOT, CliCase


class DefinitionTest(unittest.TestCase):
    def test_scaling_defaults(self):
        scaling = EXPERIMENTS["scaling"]
        self.assertEqual(scaling.sizes, (5, 10, 15, 20, 30, 50, 100))
        self.assertEqual(scaling.instances_per_size, 30)


class ExperimentCliTest(CliCase):
    def run_experiment(self, *args, expect=0):
        cmd = [sys.executable, "-m", "harness.experiment", *args,
               "--dataset", str(self.tmp / "places.txt"), "--algorithms-dir", str(self.algs),
               "--instances-dir", str(self.tmp / "instances"),
               "--results-dir", str(self.tmp / "results")]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, expect, proc.stderr)
        return proc

    def aggregates(self):
        return json.loads((self.tmp / "results" / "aggregates-scaling.json").read_text())

    def test_runs_every_algorithm_on_the_same_instances_and_tags_records(self):
        self.run_experiment("scaling", "--sizes", "1", "2", "--instances", "2")
        runs = self.index()["runs"]
        self.assertEqual(len(runs), 8)  # 2 algorithms x 2 sizes x 2 seeds
        self.assertEqual({r["instanceId"] for r in runs if r["algorithmId"] == "skip-all"},
                         {r["instanceId"] for r in runs if r["algorithmId"] == "bad-route"},
                         {"n1-seed1", "n1-seed2", "n2-seed1", "n2-seed2"})
        rec = self.record(next(r for r in runs if r["instanceId"] == "n2-seed2"))
        self.assertEqual((rec["experiment"], rec["seed"], rec["numCustomers"]), ("scaling", 2, 2))

    def test_writes_aggregates_for_the_experiment(self):
        self.run_experiment("scaling", "--sizes", "1", "2", "--instances", "2")
        agg = self.aggregates()
        self.assertEqual(agg["experiment"], "scaling")
        self.assertEqual(agg["parameters"], {"sizes": [1, 2], "instancesPerSize": 2, "seeds": [1, 2],
                                             "departureMinute": 360, "periodMinutes": 480,
                                             "speedKmh": 40.0})
        self.assertEqual(agg["sizes"], [1, 2])
        skip = next(g for g in agg["groups"] if g["algorithmId"] == "skip-all" and g["numCustomers"] == 2)
        bad = next(g for g in agg["groups"] if g["algorithmId"] == "bad-route" and g["numCustomers"] == 2)
        self.assertEqual((skip["runs"], skip["failures"], skip["visited"]["mean"]), (2, 0, 0))
        self.assertEqual((bad["runs"], bad["failures"], bad["visited"]["n"]), (2, 2, 0))

    def test_unknown_experiment_is_a_clear_error(self):
        proc = self.run_experiment("nope", expect=2)
        self.assertIn("unknown experiment", proc.stderr)


if __name__ == "__main__":
    unittest.main()
