"""Map and route-detail logic (site/js/lib/mapmodel.js), run under node. Expected values are hand-worked."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

MODEL = Path(__file__).resolve().parent.parent / "site" / "js" / "lib" / "mapmodel.js"


def node(body):
    script = f"import * as m from {json.dumps(MODEL.as_uri())};{body}"
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def call(fn, *args):
    return node(f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")


def loc(i, lat, lon, slot=None, name=None):
    d = {"id": i, "name": name or f"P{i}", "lat": lat, "lon": lon, "isDepot": slot is None}
    if slot is None:
        d.update(opensAt=0, closesAt=1440)
    else:
        d.update(slot=slot, opensAt=360 + 270 * slot, closesAt=630 + 270 * slot)
    return d


# depot 0, customers 1 (slot 0), 2 (slot 1), 3 (slot 3). Distances (km) are chosen by hand.
INST = {"departureMinute": 360, "deadlineMinute": 1440,
        "locations": [loc(0, 3.0, 101.0), loc(1, 3.0, 102.0, 0), loc(2, 4.0, 101.0, 1), loc(3, 2.0, 101.0, 3)],
        "distanceKm": [[0, 10, 20, 5], [10, 0, 7, 8], [20, 7, 0, 9], [5, 8, 9, 0]]}
RUN = {"algorithmId": "a", "valid": True, "route": [0, 1, 2, 0], "returnMinute": 700,
       "schedule": [{"id": 1, "arriveMinute": 370, "startMinute": 370, "leaveMinute": 370},
                    {"id": 2, "arriveMinute": 500, "startMinute": 630, "leaveMinute": 630}]}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class MapModelTest(unittest.TestCase):
    def test_clock_formatting(self):
        self.assertEqual(call("clock", 370.4), "06:10")
        self.assertEqual(call("clock", 1440), "24:00")
        self.assertIsNone(call("clock", None))

    def test_points_mark_visited_skipped_and_order(self):
        pts = {p["id"]: p for p in call("mapPoints", INST, RUN)}
        self.assertEqual(pts[0]["kind"], "depot")
        self.assertEqual((pts[1]["kind"], pts[1]["order"], pts[1]["arrive"], pts[1]["wait"]), ("visited", 1, 370, 0))
        self.assertEqual((pts[2]["order"], pts[2]["wait"]), (2, 130))
        self.assertEqual(pts[3]["kind"], "skipped")
        self.assertIsNone(pts[3]["order"])

    def test_no_run_or_failed_run_has_no_visits(self):
        for run in (None, {"valid": False, "route": None}):
            kinds = sorted(p["kind"] for p in call("mapPoints", INST, run))
            self.assertEqual(kinds, ["depot", "skipped", "skipped", "skipped"])

    def test_route_steps_cumulative_distance_and_return(self):
        rows = call("routeSteps", INST, RUN)
        self.assertEqual([r["id"] for r in rows], [0, 1, 2, 0])
        self.assertEqual([r["cumKm"] for r in rows], [0, 10, 17, 37])
        self.assertEqual(rows[0]["leave"], 360)
        self.assertEqual((rows[2]["arrive"], rows[2]["wait"], rows[2]["leave"]), (500, 130, 630))
        self.assertEqual(rows[3]["arrive"], 700)
        self.assertEqual(rows[1]["window"], [360, 630])
        self.assertEqual(rows[1]["slot"], 0)

    def test_slot_colours_are_four_distinct(self):
        self.assertEqual(len(set(call("slotColors"))), 4)

    def test_projection_fits_box_with_uniform_scale(self):
        pts = [{"lat": 2.0, "lon": 101.0}, {"lat": 4.0, "lon": 101.0}, {"lat": 3.0, "lon": 102.0}]
        out = call("project", pts, 400, 300, 20)
        self.assertAlmostEqual(out[0]["y"], 280, delta=0.01)   # south at the bottom
        self.assertAlmostEqual(out[1]["y"], 20, delta=0.01)    # north at the top
        self.assertGreater(out[2]["x"], out[0]["x"])           # east to the right
        self.assertAlmostEqual(out[0]["x"], out[1]["x"], delta=0.01)  # same longitude

    def test_projection_single_point_is_centred(self):
        out = call("project", [{"lat": 3, "lon": 101}], 400, 300, 20)
        self.assertEqual((out[0]["x"], out[0]["y"]), (200, 150))

    def test_algorithm_colours_are_stable_by_sorted_id(self):
        self.assertEqual(call("algorithmColorIndex", ["b", "a", "c"]), {"a": 0, "b": 1, "c": 2})

    def test_engine_falls_back_when_leaflet_load_fails(self):
        got = node("console.log(JSON.stringify(["
                   "await m.chooseEngine(() => Promise.reject(new Error('blocked')), 50),"
                   "await m.chooseEngine(() => new Promise(() => {}), 50),"
                   "await m.chooseEngine(() => Promise.resolve({}), 50),"
                   "await m.chooseEngine(() => Promise.resolve({}), 50, true)]));")
        self.assertEqual(got, ["svg", "svg", "leaflet", "svg"])


if __name__ == "__main__":
    unittest.main()
