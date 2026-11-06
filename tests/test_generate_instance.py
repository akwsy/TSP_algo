"""Instance generation, tested through the command line with a tiny fixture dataset."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def row(gid, name, lat, lon, cls="P"):
    cols = [""] * 19
    cols[0], cols[1], cols[2] = str(gid), name, name
    cols[4], cols[5], cols[6], cols[7], cols[8] = str(lat), str(lon), cls, "PPL", "MY"
    return "\t".join(cols)


# Hand-placed on the equator / meridian: one degree of arc = 6371.0088 * pi / 180 = 111.195 km.
SMALL = [
    row(1735161, "Kuala Lumpur", 0.0, 100.0),
    row(11, "East", 0.0, 101.0),    # 111.195 km from depot
    row(12, "North", 1.0, 100.0),   # 111.195 km from depot
    row(13, "Far", 0.0, 102.0),     # 222.39 km: outside the 150 km radius
    row(14, "Hill", 0.0, 100.5, cls="T"),  # near, but not a populated place
]


def many_rows(count):
    rows = [row(1735161, "Kuala Lumpur", 0.0, 100.0)]
    for i in range(count):  # tiny grid, everything within ~14 km of the depot
        rows.append(row(1000 + i, f"Town{i}", (i % 20) * 0.005, 100.0 + (i // 20) * 0.005))
    return rows


class GenerateInstanceTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def dataset(self, rows, name="places.txt"):
        path = self.tmp / name
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def run_cli(self, dataset, *args, out="instance.json"):
        out_path = self.tmp / out
        proc = subprocess.run(
            [sys.executable, "-m", "harness.generate_instance",
             "--dataset", str(dataset), "--out", str(out_path), *args],
            cwd=ROOT, capture_output=True, text=True)
        return proc, out_path

    def generate(self, rows, *args, out="instance.json"):
        proc, out_path = self.run_cli(self.dataset(rows), *args, out=out)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(out_path.read_text())

    def test_depot_is_id_zero_and_whole_day(self):
        inst = self.generate(SMALL, "--seed", "1", "--customers", "2")
        depot = inst["locations"][0]
        self.assertEqual((depot["id"], depot["name"], depot["isDepot"]), (0, "Kuala Lumpur", True))
        self.assertEqual((depot["opensAt"], depot["closesAt"]), (0, 1440))
        self.assertEqual(len(inst["locations"]), 3)
        self.assertEqual(inst["instanceId"], "n2-seed1")
        self.assertEqual(
            (inst["seed"], inst["departureMinute"], inst["periodMinutes"],
             inst["deadlineMinute"], inst["speedKmh"]),
            (1, 360, 480, 840, 40))

    def test_only_populated_places_within_150km_are_customers(self):
        inst = self.generate(SMALL, "--seed", "5", "--customers", "2")
        names = sorted(l["name"] for l in inst["locations"][1:])
        self.assertEqual(names, ["East", "North"])

    def test_distance_matrix_matches_hand_worked_haversine(self):
        inst = self.generate(SMALL, "--seed", "5", "--customers", "2")
        d = inst["distanceKm"]
        names = [l["name"] for l in inst["locations"]]
        east, north = names.index("East"), names.index("North")
        self.assertAlmostEqual(d[0][east], 111.1951, places=3)
        self.assertAlmostEqual(d[0][north], 111.1951, places=3)
        # East (0,101) to North (1,100): hand-worked haversine = 157.2 km
        self.assertAlmostEqual(d[east][north], 157.2, delta=0.1)
        for i in range(3):
            self.assertEqual(d[i][i], 0.0)
            for j in range(3):
                self.assertEqual(d[i][j], d[j][i])

    def test_slots_have_exact_boundaries_one_per_customer(self):
        inst = self.generate(many_rows(300), "--seed", "3", "--customers", "200")
        windows = {0: (360, 630), 1: (630, 900), 2: (900, 1170), 3: (1170, 1440)}
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for loc in inst["locations"][1:]:
            self.assertEqual((loc["opensAt"], loc["closesAt"]), windows[loc["slot"]])
            counts[loc["slot"]] += 1
        self.assertEqual(sum(counts.values()), 200)
        for c in counts.values():  # roughly even: expected 50 each
            self.assertTrue(25 <= c <= 75, counts)

    def test_same_seed_same_instance_different_seed_differs(self):
        rows = many_rows(300)
        a = self.generate(rows, "--seed", "7", "--customers", "10", out="a.json")
        b = self.generate(rows, "--seed", "7", "--customers", "10", out="b.json")
        c = self.generate(rows, "--seed", "8", "--customers", "10", out="c.json")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_customers_are_distinct(self):
        inst = self.generate(many_rows(300), "--seed", "2", "--customers", "100")
        ids = [l["geonameId"] for l in inst["locations"]]
        self.assertEqual(len(set(ids)), 101)

    def test_options_are_carried_through(self):
        inst = self.generate(SMALL, "--seed", "1", "--customers", "1", "--departure", "400",
                             "--period", "300", "--speed", "60")
        self.assertEqual((inst["departureMinute"], inst["periodMinutes"],
                          inst["deadlineMinute"], inst["speedKmh"]), (400, 300, 700, 60))

    def assertRejected(self, rows, *args, expect):
        proc, out_path = self.run_cli(self.dataset(rows), *args)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(expect, proc.stderr)
        self.assertFalse(out_path.exists())

    def test_departure_plus_period_over_1440_rejected(self):
        self.assertRejected(SMALL, "--seed", "1", "--customers", "1",
                            "--departure", "1000", "--period", "500", expect="1440")

    def test_other_invalid_configs_rejected(self):
        self.assertRejected(SMALL, "--customers", "1", expect="seed")
        self.assertRejected(SMALL, "--seed", "1", "--customers", "0", expect="customers")
        self.assertRejected(SMALL, "--seed", "1", "--speed", "0", expect="speed")
        self.assertRejected(SMALL, "--seed", "1", "--period", "0", expect="period")
        self.assertRejected(SMALL, "--seed", "1", "--departure", "-5", expect="departure")

    def test_too_few_candidates_rejected(self):
        self.assertRejected(SMALL, "--seed", "1", "--customers", "3", expect="candidate")

    def test_malformed_dataset_rows_rejected_with_line_number(self):
        short = SMALL[:2] + ["12\tonly\tthree"] + SMALL[2:]
        self.assertRejected(short, "--seed", "1", "--customers", "1", expect="line 3")
        bad_lat = SMALL[:1] + [row(11, "East", "north", 101.0)]
        self.assertRejected(bad_lat, "--seed", "1", "--customers", "1", expect="line 2")


if __name__ == "__main__":
    unittest.main()
