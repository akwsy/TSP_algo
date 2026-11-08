import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALGO_DIR = ROOT / "algorithms" / "nearest-neighbour"
sys.path.insert(0, str(ROOT))
from harness.validator import validate_route  # noqa: E402


def run_algo(instance):
    meta = json.loads((ALGO_DIR / "algorithm.json").read_text())
    return subprocess.run(meta["command"], cwd=ALGO_DIR, input=json.dumps(instance),
                          capture_output=True, text=True, timeout=30)


def tiny(dist, windows, deadline=1440):
    """Speed 60 km/h so 1 km = 1 minute. Depart at minute 0."""
    locs = [{"id": 0, "isDepot": True, "opensAt": 0, "closesAt": 1440}]
    for i, (o, c) in enumerate(windows, start=1):
        locs.append({"id": i, "isDepot": False, "opensAt": o, "closesAt": c})
    return {"instanceId": "t", "seed": 1, "departureMinute": 0, "periodMinutes": deadline,
            "deadlineMinute": deadline, "speedKmh": 60, "timeLimitSeconds": 10,
            "locations": locs, "distanceKm": dist}


LINE = [[0, 10, 20], [10, 0, 10], [20, 10, 0]]


class TinyInstances(unittest.TestCase):
    def route(self, inst):
        proc = run_algo(inst)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_visits_nearest_first_then_returns(self):
        out = self.route(tiny(LINE, [(0, 1440), (0, 1440)]))
        self.assertEqual(out["route"], [0, 1, 2, 0])
        self.assertEqual(out["status"], "HEURISTIC")

    def test_ties_broken_by_lowest_id(self):
        inst = tiny([[0, 10, 10], [10, 0, 5], [10, 5, 0]], [(0, 1440), (0, 1440)])
        self.assertEqual(self.route(inst)["route"], [0, 1, 2, 0])

    def test_skips_customer_whose_window_has_closed(self):
        out = self.route(tiny(LINE, [(0, 5), (0, 1440)]))
        self.assertEqual(out["route"], [0, 2, 0])

    def test_waits_for_opening_when_still_feasible(self):
        out = self.route(tiny(LINE, [(100, 200), (0, 1440)]))
        self.assertEqual(out["route"], [0, 1, 2, 0])

    def test_return_trip_must_fit_deadline(self):
        # reach 1 at 10 (home at 20 ok); 2 from 1 at 20, home at 40 > 25
        out = self.route(tiny(LINE, [(0, 1440), (0, 1440)], deadline=25))
        self.assertEqual(out["route"], [0, 1, 0])

    def test_waiting_counts_against_deadline(self):
        # customer 1 opens at 30; start 30, home at 40 > 35. Customer 2 is fine (home at 24).
        near = [[0, 10, 12], [10, 0, 10], [12, 10, 0]]
        out = self.route(tiny(near, [(30, 1440), (0, 1440)], deadline=35))
        self.assertEqual(out["route"], [0, 2, 0])

    def test_nobody_reachable_gives_depot_to_depot(self):
        out = self.route(tiny(LINE, [(0, 5), (0, 5)]))
        self.assertEqual(out["route"], [0, 0])


class GeneratedInstances(unittest.TestCase):
    def generate(self, seed, customers):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "i.json"
            subprocess.run([sys.executable, "-m", "harness.generate_instance", "--seed", str(seed),
                            "--customers", str(customers), "--out", str(path)],
                           cwd=ROOT, check=True, capture_output=True)
            return json.loads(path.read_text())

    def test_routes_feasible_deterministic_never_optimal(self):
        for seed in range(1, 9):
            for n in (5, 10, 25):
                inst = self.generate(seed, n)
                a, b = run_algo(inst), run_algo(inst)
                self.assertEqual(a.returncode, 0, a.stderr)
                self.assertEqual(a.stdout, b.stdout)
                out = json.loads(a.stdout)
                self.assertNotEqual(out["status"], "OPTIMAL")
                res = validate_route(inst, out["route"])
                self.assertTrue(res["valid"], (seed, n, res["failureReason"]))


class Metadata(unittest.TestCase):
    def test_labelled_as_baseline(self):
        meta = json.loads((ALGO_DIR / "algorithm.json").read_text())
        self.assertEqual(meta["id"], "nearest-neighbour")
        self.assertIn("baseline", meta["displayName"].lower())
        self.assertIn("baseline", meta["description"].lower())
        self.assertFalse(meta["exact"])
        self.assertIn("time", meta["complexity"])
        self.assertIn("space", meta["complexity"])


if __name__ == "__main__":
    unittest.main()
