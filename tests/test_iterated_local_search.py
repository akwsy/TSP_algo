import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALGO_DIR = ROOT / "algorithms" / "iterated-local-search"
GREEDY_DIR = ROOT / "algorithms" / "greedy-insertion-cached"
sys.path.insert(0, str(ROOT))
from harness.validator import validate_route  # noqa: E402


def run_algo(instance, algo_dir=ALGO_DIR):
    meta = json.loads((algo_dir / "algorithm.json").read_text())
    return subprocess.run(meta["command"], cwd=algo_dir, input=json.dumps(instance),
                          capture_output=True, text=True, timeout=60)


def tiny(dist, windows, deadline=1440):
    """Speed 60 km/h so 1 km = 1 minute. Depart at minute 0."""
    locs = [{"id": 0, "geonameId": 0, "isDepot": True, "opensAt": 0, "closesAt": 1440}]
    for i, (o, c) in enumerate(windows, start=1):
        locs.append({"id": i, "geonameId": i, "isDepot": False, "opensAt": o, "closesAt": c})
    return {"instanceId": "t", "seed": 1, "departureMinute": 0, "periodMinutes": deadline,
            "deadlineMinute": deadline, "speedKmh": 60, "timeLimitSeconds": 10,
            "locations": locs, "distanceKm": dist}


LINE = [[0, 10, 20], [10, 0, 10], [20, 10, 0]]


class TinyInstances(unittest.TestCase):
    def route(self, inst):
        proc = run_algo(inst)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        res = validate_route(inst, out["route"])
        self.assertTrue(res["valid"], res["failureReason"])
        self.assertEqual(out["status"], "HEURISTIC")
        return out["route"]

    def test_visits_everyone_when_all_fit(self):
        route = self.route(tiny(LINE, [(0, 1440), (0, 1440)]))
        self.assertEqual(sorted(route), [0, 0, 1, 2])

    def test_skips_customer_whose_window_has_closed(self):
        self.assertEqual(self.route(tiny(LINE, [(0, 5), (0, 1440)])), [0, 2, 0])

    def test_waits_for_opening_when_still_feasible(self):
        route = self.route(tiny(LINE, [(100, 200), (0, 1440)]))
        self.assertEqual(sorted(route), [0, 0, 1, 2])

    def test_return_trip_must_fit_deadline(self):
        self.assertEqual(self.route(tiny(LINE, [(0, 1440), (0, 1440)], deadline=25)), [0, 1, 0])

    def test_waiting_counts_against_deadline(self):
        # customer 1 opens at 30; start 30, home at 40 > 35. Customer 2 is fine (home at 24).
        near = [[0, 10, 12], [10, 0, 10], [12, 10, 0]]
        self.assertEqual(self.route(tiny(near, [(30, 1440), (0, 1440)], deadline=35)), [0, 2, 0])

    def test_nobody_reachable_gives_depot_to_depot(self):
        self.assertEqual(self.route(tiny(LINE, [(0, 5), (0, 5)])), [0, 0])

    def test_no_customers_gives_depot_to_depot(self):
        self.assertEqual(self.route(tiny([[0]], [])), [0, 0])


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

    def test_never_visits_fewer_than_distance_greedy_in_total(self):
        ils_total = greedy_total = 0
        for seed in range(1, 6):
            inst = self.generate(seed, 30)
            ils = validate_route(inst, json.loads(run_algo(inst).stdout)["route"])
            greedy = validate_route(inst, json.loads(run_algo(inst, GREEDY_DIR).stdout)["route"])
            ils_total += ils["visited"]
            greedy_total += greedy["visited"]
        self.assertGreaterEqual(ils_total, greedy_total)


class Metadata(unittest.TestCase):
    def test_metadata(self):
        meta = json.loads((ALGO_DIR / "algorithm.json").read_text())
        self.assertEqual(meta["id"], "iterated-local-search")
        self.assertFalse(meta["exact"])
        self.assertIn("time", meta["complexity"])
        self.assertIn("space", meta["complexity"])


if __name__ == "__main__":
    unittest.main()
