"""Experiment command, tested end to end with the tiny fixture dataset."""
import contextlib
import io
import json
import subprocess
import sys
import unittest

from harness import experiment
from harness.experiments import EXPERIMENTS, Experiment
from test_run import ROOT, CliCase


class DefinitionTest(unittest.TestCase):
    def test_scaling_defaults(self):
        scaling = EXPERIMENTS["scaling"]
        self.assertEqual(scaling.sizes, (5, 10, 15, 20, 30, 50, 100))
        self.assertEqual(scaling.values, scaling.sizes)
        self.assertEqual(scaling.instances_per_size, 30)


class SuiteDefinitionTest(unittest.TestCase):
    def test_the_six_experiments_in_order(self):
        self.assertEqual(list(EXPERIMENTS), ["scaling", "time-budget", "speed", "window-alignment",
                                             "spread", "stress"])
        got = {n: (e.param, e.values, e.instances_per_size, e.fixed) for n, e in EXPERIMENTS.items()}
        self.assertEqual(got, {
            "scaling": ("customers", (5, 10, 15, 20, 30, 50, 100), 30, {}),
            "time-budget": ("period", (240, 480, 720, 960, 1080), 30, {"customers": 30}),
            "speed": ("speed", (20, 30, 40, 60, 80), 30, {"customers": 30}),
            "window-alignment": ("departure", (360, 540, 720, 900, 1080), 30,
                                 {"customers": 30, "period": 360}),
            "spread": ("radius", (25, 50, 100, 150, 250), 30, {"customers": 20}),
            "stress": ("customers", (100, 150, 200, 300), 10, {})})

    def test_config_varies_only_the_swept_parameter_and_names_it_in_the_instance_id(self):
        e = EXPERIMENTS
        self.assertEqual(e["scaling"].config(3, 20).instance_id, "n20-seed3")
        self.assertEqual(e["time-budget"].config(3, 480).instance_id, "n30-seed3-per480")
        self.assertEqual(e["speed"].config(3, 20).instance_id, "n30-seed3-spd20")
        self.assertEqual(e["window-alignment"].config(3, 540).instance_id, "n30-seed3-dep540-per360")
        self.assertEqual(e["spread"].config(3, 50).instance_id, "n20-seed3-rad50")
        self.assertEqual(e["spread"].config(3, 150).instance_id, "n20-seed3")  # default radius

    def test_every_configuration_is_valid(self):
        for exp in EXPERIMENTS.values():
            for v in exp.values:
                c = exp.config(1, v)
                self.assertLessEqual(c.deadline_minute, 1440, (exp.name, v))

    def test_fixed_may_not_repeat_the_swept_parameter_or_name_unknown_ones(self):
        with self.assertRaises(ValueError):
            Experiment("x", "", "speed", (1,), 1, fixed={"speed": 3})
        with self.assertRaises(ValueError):
            Experiment("x", "", "weather", (1,), 1)


class SweepCliTest(CliCase):
    def run_main(self, args, experiments=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = experiment.main(args + [
                "--dataset", str(self.tmp / "places.txt"), "--algorithms-dir", str(self.algs),
                "--instances-dir", str(self.tmp / "instances"),
                "--results-dir", str(self.tmp / "results")], experiments=experiments)
        self.assertEqual(code, 0)
        return buf.getvalue()

    def small(self):
        return {e.name: e for e in (
            Experiment("alpha", "customers sweep", "customers", (1, 2), 2),
            Experiment("beta", "period sweep", "period", (240, 480), 2, fixed={"customers": 2}))}

    def read(self, name):
        return json.loads((self.tmp / "results" / name).read_text())

    def test_sweep_values_are_recorded_on_runs_and_index_entries(self):
        self.run_main(["beta"], self.small())
        runs = self.index()["runs"]
        self.assertEqual(len(runs), 8)  # 2 algorithms x 2 periods x 2 seeds
        self.assertEqual({r["instanceId"] for r in runs},
                         {f"n2-seed{s}-per{p}" for s in (1, 2) for p in (240, 480)})
        entry = next(r for r in runs if r["instanceId"] == "n2-seed2-per480")
        rec = self.record(entry)
        for d in (entry, rec):
            self.assertEqual((d["experiment"], d["sweepParam"], d["sweepValue"]), ("beta", "period", 480))
        self.assertEqual(rec["numCustomers"], 2)

    def test_customers_sweep_has_sweep_value_equal_to_num_customers(self):
        self.run_main(["alpha"], self.small())
        for e in self.index()["runs"]:
            self.assertEqual((e["sweepParam"], e["sweepValue"]), ("customers", e["numCustomers"]))

    def test_sweep_aggregates_pairs_and_parameters(self):
        self.run_main(["beta", "--values", "480", "--instances", "2"], self.small())
        agg = self.read("aggregates-beta.json")
        self.assertEqual(agg["parameters"], {
            "sweepParam": "period", "values": [480], "instancesPerSize": 2, "seeds": [1, 2],
            "customers": 2, "departureMinute": 360, "speedKmh": 40.0, "radiusKm": 150.0})
        self.assertEqual(agg["sweepValues"], [480])
        self.assertEqual({(g["algorithmId"], g["sweepValue"], g["numCustomers"]) for g in agg["groups"]},
                         {("skip-all", 480, 2), ("bad-route", 480, 2)})
        # bad-route is invalid on both instances, so nothing can be paired.
        self.assertEqual(len(agg["pairs"]), 1)
        p = agg["pairs"][0]
        self.assertEqual((p["a"], p["b"], p["sweepValue"], p["instances"], p["excluded"]),
                         ("bad-route", "skip-all", 480, 0, 2))

    def test_scaling_style_aggregates_keep_their_old_fields(self):
        self.run_main(["alpha", "--full-run-instances", "0"], self.small())
        agg = self.read("aggregates-alpha.json")
        self.assertEqual(agg["parameters"]["sizes"], [1, 2])
        self.assertEqual((agg["sizes"], agg["sweepValues"]), ([1, 2], [1, 2]))
        self.assertEqual(len(agg["pairs"]), 2)

    def test_suite_runs_every_experiment_and_writes_suite_json(self):
        out = self.run_main(["suite", "--full-run-instances", "0"], self.small())
        suite = self.read("suite.json")
        self.assertEqual([e["name"] for e in suite["experiments"]], ["alpha", "beta"])
        beta = suite["experiments"][1]
        self.assertEqual({k: beta[k] for k in ("name", "description", "param", "values",
                                                "instancesPerSize", "algorithms", "aggregates")},
                         {"name": "beta", "description": "period sweep", "param": "period",
                          "values": [240, 480], "instancesPerSize": 2,
                          "algorithms": ["bad-route", "skip-all"],
                          "aggregates": "aggregates-beta.json"})
        self.assertRegex(beta["timestamp"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
        self.assertTrue((self.tmp / "results" / "aggregates-alpha.json").exists())
        self.assertTrue((self.tmp / "results" / "aggregates-beta.json").exists())
        # one progress line per sweep value, not per run
        self.assertEqual(sum(1 for l in out.splitlines() if l.startswith("[beta] period=")), 2)
        self.assertNotIn("skip-all on ", out)

    def test_list_prints_every_experiment(self):
        out = self.run_main(["--list"], self.small())
        self.assertIn("alpha", out)
        self.assertIn("beta", out)
        self.assertIn("period", out)

    def test_fixed_override_and_values_override(self):
        self.run_main(["beta", "--values", "240", "--instances", "1", "--fixed", "customers=1"],
                      self.small())
        self.assertEqual({r["instanceId"] for r in self.index()["runs"]}, {"n1-seed1-per240"})

    def test_same_aggregates_pairs_on_a_second_run(self):
        self.run_main(["beta", "--force"], self.small())
        first = self.read("aggregates-beta.json")["pairs"]
        self.run_main(["beta", "--force"], self.small())
        self.assertEqual(self.read("aggregates-beta.json")["pairs"], first)


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
                                             "departureMinute": 360, "periodMinutes": 1080,
                                             "speedKmh": 40.0, "radiusKm": 150.0,
                                             "sweepParam": "customers", "values": [1, 2]})
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
