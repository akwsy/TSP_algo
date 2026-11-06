"""Runner, tested through the command line with a tiny fixture dataset."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_generate_instance import row

ROOT = Path(__file__).resolve().parent.parent

# Two customers, each 111.195 km (one degree of arc) from the depot.
DATASET = [
    row(1735161, "Kuala Lumpur", 0.0, 100.0),
    row(11, "East", 0.0, 101.0),
    row(12, "North", 1.0, 100.0),
]

SKIP_ALL = ('import json,sys\njson.load(sys.stdin)\n'
            'print(json.dumps({"route":[0,0],"status":"HEURISTIC",'
            '"distanceKm":999,"visited":99,"stats":{"iterations":7}}))\n')
BAD_ROUTE = 'import sys\nprint(\'{"route":[0,5,0],"status":"HEURISTIC"}\')\n'


def write_algorithm(root, alg_id, source):
    folder = root / alg_id
    folder.mkdir(parents=True)
    (folder / "solve.py").write_text(source)
    (folder / "algorithm.json").write_text(json.dumps({
        "id": alg_id, "displayName": alg_id, "command": ["python3", "solve.py"],
        "timeLimitSeconds": 10}))


class CliCase(unittest.TestCase):
    """Shared CLI helpers; no tests of its own."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        (self.tmp / "places.txt").write_text("\n".join(DATASET) + "\n")
        self.algs = self.tmp / "algs"
        write_algorithm(self.algs, "skip-all", SKIP_ALL)
        write_algorithm(self.algs, "bad-route", BAD_ROUTE)

    def run_cli(self, *args, algorithms=True):
        cmd = [sys.executable, "-m", "harness.run", "--dataset", str(self.tmp / "places.txt"),
               "--instances-dir", str(self.tmp / "instances"),
               "--results-dir", str(self.tmp / "results"), "--customers", "2", *args]
        if algorithms:
            cmd += ["--algorithms-dir", str(self.algs)]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def index(self):
        return json.loads((self.tmp / "results" / "index.json").read_text())

    def record(self, entry):
        return json.loads((self.tmp / "results" / entry["file"]).read_text())

    def entry(self, alg, seed):
        return next(e for e in self.index()["runs"]
                    if e["algorithmId"] == alg and e["instanceId"] == f"n2-seed{seed}")


class RunTest(CliCase):
    def test_metrics_come_from_the_validator_and_runtime_from_the_harness(self):
        self.run_cli("--seeds", "1")
        rec = self.record(self.entry("skip-all", 1))
        # Route [0,0] visits nobody: hand-worked, and the algorithm's own claims are ignored.
        self.assertEqual(
            (rec["valid"], rec["visited"], rec["skipped"], rec["distanceKm"], rec["totalMinutes"],
             rec["returnMinute"], rec["route"], rec["status"], rec["stats"]),
            (True, 0, [1, 2], 0, 0, 360, [0, 0], "HEURISTIC", {"iterations": 7}))
        for key in ("algorithmId", "instanceId", "commit", "timestamp", "failureReason",
                    "travelMinutes", "waitMinutes", "schedule"):
            self.assertIn(key, rec)
        self.assertGreater(rec["runtimeMs"], 0)

    def test_invalid_route_is_recorded_as_failure_without_crashing(self):
        self.run_cli("--seeds", "1")
        rec = self.record(self.entry("bad-route", 1))
        self.assertFalse(rec["valid"])
        self.assertIn("unknown location id 5", rec["failureReason"])
        self.assertIsNone(rec["distanceKm"])
        self.assertEqual(rec["route"], [0, 5, 0])

    def test_every_algorithm_gets_every_instance_and_index_lists_all_runs(self):
        self.run_cli("--seeds", "1", "2")
        runs = self.index()["runs"]
        self.assertEqual(len(runs), 4)
        self.assertEqual({(r["algorithmId"], r["instanceId"]) for r in runs},
                         {(a, f"n2-seed{s}") for a in ("skip-all", "bad-route") for s in (1, 2)})
        for r in runs:
            self.assertIn("commit", r)
            self.assertTrue(r["timestamp"])
            self.assertIn("valid", r)
        self.assertEqual(len(list((self.tmp / "instances").glob("*.json"))), 2)

    def test_real_baseline_runs_from_its_own_folder(self):
        self.run_cli("--seeds", "1", algorithms=False)
        rec = self.record(self.entry("nearest-neighbour", 1))
        self.assertTrue(rec["valid"], rec["failureReason"])
        self.assertRegex(rec["commit"], r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
