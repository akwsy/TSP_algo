"""Map and route-detail logic (site/js/lib/mapmodel.js), run under node. Expected values are hand-worked."""
import json
import re
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


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SceneTest(unittest.TestCase):
    def test_scene_combines_shown_runs(self):
        other = {"algorithmId": "b", "valid": True, "route": [0, 3, 0], "returnMinute": 500,
                 "schedule": [{"id": 3, "arriveMinute": 1180, "startMinute": 1180, "leaveMinute": 1180}]}
        scene = call("buildScene", INST, [{"id": "a", "label": "A", "run": RUN}, {"id": "b", "label": "B", "run": other}])
        pts = {p["id"]: p for p in scene["points"]}
        self.assertTrue(pts[3]["filled"] and pts[1]["filled"])
        self.assertEqual(pts[3]["info"], ["A: skipped", "B: stop 1, arrives 19:40, no wait"])
        self.assertEqual(pts[2]["info"][0], "A: stop 2, arrives 08:20, waits 130 min")
        self.assertTrue(pts[0]["depot"] and pts[0]["info"] == [])
        self.assertEqual([l["ids"] for l in scene["lines"]], [[0, 1, 2, 0], [0, 3, 0]])
        self.assertEqual(len(scene["badges"]), 3)

    def test_places_done_on_earlier_days_are_marked_done_only_when_every_shown_run_has_them(self):
        a = {"id": "a", "label": "A", "run": RUN, "day": 2, "done": [3]}
        b = {"id": "b", "label": "B", "run": {"valid": False, "route": None}, "day": 2, "done": [3, 2]}
        pts = {p["id"]: p for p in call("buildScene", INST, [a, b])["points"]}
        self.assertTrue(pts[3]["done"] and not pts[3]["filled"])
        self.assertFalse(pts[2]["done"])  # visited today by A (filled) and done earlier for B
        self.assertFalse(pts[1]["done"])
        self.assertFalse(pts[0]["done"])
        only = {p["id"]: p for p in call("buildScene", INST, [a, {**b, "done": []}])["points"]}
        self.assertFalse(only[3]["done"])

    def test_stop_line_for_a_full_run_day(self):
        self.assertEqual(call("dayStopLine", {"run": RUN, "day": 2, "done": [3]}, INST, 3), "done on an earlier day")
        self.assertEqual(call("dayStopLine", {"run": RUN, "day": 2, "done": []}, INST, 3), "still to visit")
        self.assertEqual(call("dayStopLine", {"run": RUN, "day": 2, "done": []}, INST, 1), "Arrive 06:10 \u00b7 No wait \u00b7 Leave 06:10")
        self.assertEqual(call("dayStopLine", {"run": RUN}, INST, 3), "not visited")

    def test_failed_run_draws_no_route_and_nothing_filled(self):
        scene = call("buildScene", INST, [{"id": "a", "label": "A", "run": {"valid": False, "route": None}}])
        self.assertEqual(scene["lines"], [])
        self.assertFalse(any(p["filled"] for p in scene["points"]))


def ent(i, visited, km, minutes=100, valid=True, skipped=()):
    return {"id": i, "label": i.upper(), "run": {"valid": valid, "route": [0, 1, 0], "visited": visited, "distanceKm": km,
            "totalMinutes": minutes, "skipped": list(skipped)}}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CompareModelTest(unittest.TestCase):
    def test_lane_offsets_are_centred_and_spaced(self):
        self.assertEqual(call("laneOffsets", 1, 4), [0])
        self.assertEqual(call("laneOffsets", 3, 4), [-4, 0, 4])
        self.assertEqual(call("laneOffsets", 2, 4), [-2, 2])

    def test_offset_segment_moves_both_ends_to_the_left_of_travel(self):
        # Heading east (+x) in screen space (y down): left of travel is up (-y).
        self.assertEqual(call("offsetSegment", {"x": 0, "y": 0}, {"x": 10, "y": 0}, 3),
                         [{"x": 0, "y": -3}, {"x": 10, "y": -3}])
        self.assertEqual(call("offsetSegment", {"x": 5, "y": 5}, {"x": 5, "y": 5}, 3),
                         [{"x": 5, "y": 5}, {"x": 5, "y": 5}])

    def test_best_is_most_visited_then_shortest_distance_and_skips_failures(self):
        es = [ent("a", 3, 50), ent("b", 4, 90), ent("c", 4, 80), ent("d", 9, 1, valid=False)]
        self.assertEqual(call("bestEntryId", es), "c")
        self.assertIsNone(call("bestEntryId", [ent("d", 9, 1, valid=False)]))

    def test_summary_rows_in_plain_numbers(self):
        rows = call("summaryRows", [ent("a", 3, 50.04, 125), ent("b", 4, 90, 61)])
        self.assertEqual([(r["id"], r["visited"], r["best"]) for r in rows], [("a", 3, False), ("b", 4, True)])
        self.assertEqual(rows[0]["distance"], "50 km")
        self.assertEqual(rows[0]["time"], "2 h 5 min")
        self.assertEqual(rows[1]["time"], "1 h 1 min")
        self.assertEqual(call("summaryRows", [ent("x", 1, 5, 45)])[0]["time"], "45 min")

    def test_only_visited_notes_name_places_nobody_else_visited(self):
        other = {**RUN, "route": [0, 3, 1, 0], "schedule": [
            {"id": 3, "arriveMinute": 1180, "startMinute": 1180, "leaveMinute": 1180},
            {"id": 1, "arriveMinute": 1200, "startMinute": 1200, "leaveMinute": 1200}]}
        es = [{"id": "a", "label": "A", "run": RUN}, {"id": "b", "label": "B", "run": other}]
        self.assertEqual(call("differenceNotes", INST, es), ["Only A visited: P2", "Only B visited: P3"])
        self.assertEqual(call("differenceNotes", INST, es[:1]), [])
        same = [es[0], {"id": "c", "label": "C", "run": RUN}]
        self.assertEqual(call("differenceNotes", INST, same), [])

    def test_label_plan_keeps_visited_first_and_drops_overlaps(self):
        pts = [{"id": 1, "name": "Alpha", "x": 50, "y": 50, "visited": False},
               {"id": 2, "name": "Beta", "x": 52, "y": 52, "visited": True},
               {"id": 3, "name": "Gamma", "x": 300, "y": 200, "visited": False}]
        self.assertEqual(sorted(call("labelPlan", pts, 640, 480)), [2, 3])

    def test_label_plan_keeps_labels_inside_the_box(self):
        pts = [{"id": 1, "name": "Far east town", "x": 636, "y": 50, "visited": True}]
        self.assertEqual(call("labelPlan", pts, 640, 480), [1])
        self.assertEqual(call("labelSide", pts[0], 640), "left")
        self.assertEqual(call("labelSide", {**pts[0], "x": 20}, 640), "right")

    def test_labels_show_one_zoom_level_past_the_initial_fit(self):
        self.assertFalse(call("labelsVisible", 6, 6, 11))
        self.assertTrue(call("labelsVisible", 7, 6, 11))
        self.assertTrue(call("labelsVisible", 9, 6, 11))
        self.assertFalse(call("labelsVisible", 5, 6, 11))

    def test_labels_threshold_is_always_reachable_within_max_zoom(self):
        self.assertTrue(call("labelsVisible", 11, 11, 11))
        self.assertTrue(call("labelsVisible", 11, 12, 11))
        self.assertFalse(call("labelsVisible", 10, 11, 11))

    def test_faded_outline_keeps_three_to_one_contrast_in_both_themes(self):
        css = (MODEL.parent.parent.parent / "css" / "style.css").read_text()
        light = dict(re.findall(r"--(bg|text):\s*(#[0-9a-f]{6})", css.split(':root[data-theme="dark"]')[0]))
        dark = dict(re.findall(r"--(bg|text):\s*(#[0-9a-f]{6})", css.split(':root[data-theme="dark"]')[1].split("}")[0]))
        opacity = node("console.log(m.FADED_OPACITY)")
        self.assertTrue(0.4 <= opacity <= 0.6)
        for theme in (light, dark):
            self.assertGreaterEqual(call("contrastRatio", theme["text"], theme["bg"], opacity), 3.0)
        # worked values: black on white is 21:1; black at half opacity is #808080 on white, 3.95:1
        self.assertAlmostEqual(call("contrastRatio", "#000000", "#ffffff", 1), 21, places=1)
        self.assertAlmostEqual(call("contrastRatio", "#000000", "#ffffff", 0.5), 3.95, places=1)

    def test_tile_limits_stop_native_zoom_where_the_provider_has_real_tiles(self):
        # Esri World Terrain Base serves a "Map data not yet available" placeholder from level 10 up, so level 9 is the last real one.
        lim = node("console.log(JSON.stringify(m.TILE_LIMITS));")
        self.assertEqual(lim["maxNativeZoom"], 9)
        self.assertGreater(lim["maxZoom"], lim["maxNativeZoom"])
        self.assertLessEqual(lim["maxZoom"] - lim["maxNativeZoom"], 4)

    def test_clamp_zoom_stays_inside_the_limits(self):
        self.assertEqual(call("clampZoom", 99, 1, 13), 13)
        self.assertEqual(call("clampZoom", -3, 1, 13), 1)
        self.assertEqual(call("clampZoom", 7.5, 1, 13), 7.5)
        self.assertEqual(call("clampZoom", None, 1, 13), 1)


# Worked example from docs/ALGORITHM_SPEC.md section 8: route [0,1,3,2,0], departure 06:00 (360).
SPEC_INST = {"departureMinute": 360, "deadlineMinute": 1440, "speedKmh": 40,
             "locations": [dict(loc(0, 3, 101), name="Depot"), dict(loc(1, 3, 102, 0), name="Alpha"),
                           dict(loc(2, 4, 101, 1), name="Beta", opensAt=1170, closesAt=1300),
                           dict(loc(3, 2, 101, 3), name="Gamma", opensAt=630, closesAt=900)],
             "distanceKm": [[0, 47.45, 30, 40], [47.45, 0, 20, 92.62], [30, 20, 0, 25], [40, 92.62, 25, 0]]}
SPEC_RUN = {"valid": True, "route": [0, 1, 3, 2, 0], "returnMinute": 1264.73,
            "schedule": [{"id": 1, "arriveMinute": 431.18, "startMinute": 431.18, "leaveMinute": 431.18},
                         {"id": 3, "arriveMinute": 570.11, "startMinute": 630, "leaveMinute": 630},
                         {"id": 2, "arriveMinute": 855.16, "startMinute": 1170, "leaveMinute": 1170}]}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class HoverDetailsTest(unittest.TestCase):
    def test_format_clock_and_duration(self):
        self.assertEqual(call("formatClock", 431.18), "07:11")
        self.assertEqual(call("formatClock", 5), "00:05")
        self.assertEqual([call("formatDuration", v) for v in (0, 0.4, 45, 60, 72, 138.94, 315)],
                         ["0 min", "0 min", "45 min", "1 h", "1 h 12 min", "2 h 19 min", "5 h 15 min"])

    def test_stop_with_no_wait(self):
        t = call("stopTimes", SPEC_RUN, SPEC_INST, 1)
        self.assertEqual((t["visited"], t["arrive"], t["wait"], t["leave"]), (True, "07:11", "No wait", "07:11"))

    def test_stop_with_wait_adds_up(self):
        t = call("stopTimes", SPEC_RUN, SPEC_INST, 3)
        self.assertEqual((t["arrive"], t["wait"], t["leave"]), ("09:30", "Waited 1 h", "10:30"))
        t = call("stopTimes", SPEC_RUN, SPEC_INST, 2)
        self.assertEqual((t["arrive"], t["wait"], t["leave"]), ("14:15", "Waited 5 h 15 min", "19:30"))

    def test_wait_is_from_shown_times_so_it_always_adds_up(self):
        run = {"valid": True, "route": [0, 1, 0], "returnMinute": 700,
               "schedule": [{"id": 1, "arriveMinute": 570.4, "startMinute": 629.8, "leaveMinute": 629.8}]}
        t = call("stopTimes", run, SPEC_INST, 1)
        # 09:30 and 10:30 are shown, so the wait shown is exactly one hour (not 59 min)
        self.assertEqual((t["arrive"], t["wait"], t["leave"]), ("09:30", "Waited 1 h", "10:30"))

    def test_depot_and_skipped_stop(self):
        d = call("stopTimes", SPEC_RUN, SPEC_INST, 0)
        self.assertEqual((d["depot"], d["leave"], d["back"]), (True, "06:00", "21:05"))
        run = dict(SPEC_RUN, route=[0, 1, 0], returnMinute=700)
        self.assertFalse(call("stopTimes", run, SPEC_INST, 2)["visited"])
        self.assertFalse(call("stopTimes", None, SPEC_INST, 2)["visited"])

    def test_leg_between_stops(self):
        g = call("legDetails", SPEC_RUN, SPEC_INST, 1, 3)
        self.assertEqual((g["from"], g["to"]), ("Alpha", "Gamma"))
        self.assertEqual((g["depart"], g["arrive"], g["travel"], g["distance"]), ("07:11", "09:30", "2 h 19 min", "92.6 km"))
        self.assertEqual(g["opens"], "10:30-15:00")
        self.assertEqual(g["then"], "then waits 1 h")

    def test_first_leg_leaves_at_departure_and_last_returns_to_depot(self):
        g = call("legDetails", SPEC_RUN, SPEC_INST, 0, 1)
        self.assertEqual((g["depart"], g["arrive"], g["travel"], g["then"]), ("06:00", "07:11", "1 h 11 min", None))
        g = call("legDetails", SPEC_RUN, SPEC_INST, 2, 0)
        self.assertEqual((g["depart"], g["arrive"], g["travel"], g["opens"], g["to"]), ("19:30", "21:05", "1 h 35 min", "open all day", "Depot"))

    def test_stop_line_wording(self):
        self.assertEqual(call("stopLine", call("stopTimes", SPEC_RUN, SPEC_INST, 3)), "Arrive 09:30 · Waited 1 h · Leave 10:30")
        self.assertEqual(call("stopLine", call("stopTimes", SPEC_RUN, SPEC_INST, 0)), "Leave 06:00 · Back 21:05")
        self.assertEqual(call("stopLine", call("stopTimes", None, SPEC_INST, 3)), "not visited")

    def test_leg_rows_wording(self):
        rows = call("legRows", call("legDetails", SPEC_RUN, SPEC_INST, 1, 3))
        self.assertEqual(rows, [["Travel time", "2 h 19 min"], ["Departure", "07:11"], ["Arrival", "09:30 (then waits 1 h)"],
                                ["Opening hours", "10:30-15:00"], ["Distance", "92.6 km"]])

    def test_unknown_leg_is_null(self):
        self.assertIsNone(call("legDetails", SPEC_RUN, SPEC_INST, 1, 2))


if __name__ == "__main__":
    unittest.main()
