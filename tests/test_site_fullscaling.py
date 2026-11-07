"""Series and wording for the full-run Scaling charts (site/js/lib/fullscaling.js), run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "site" / "js" / "lib"


def call(fn, *args):
    script = (f"import * as m from {json.dumps((LIB / 'fullscaling.js').as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def stat(mean, std, n):
    return {"mean": mean, "std": std, "n": n}


def group(alg, size, finished, stopped, hours=None, std=None, ms=None):
    n = finished
    return {"algorithmId": alg, "numCustomers": size, "finished": finished, "stopped": stopped,
            "workingHours": stat(hours, std, n), "days": stat(None if hours is None else hours / 8, None, n),
            "totalDistanceKm": stat(None if hours is None else hours * 10, None, n),
            "totalRuntimeMs": stat(ms, std, n)}


FULL = {"groups": [
    group("b", 10, 3, 0, 4.0, 1.0, 2000), group("b", 20, 1, 2, 9.0, None, 4000), group("b", 30, 0, 3),
    group("a", 10, 2, 1, 3.0, 0.5, 500), group("a", 20, 2, 0, 5.0, 0.5, 700)]}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class FullSeriesTest(unittest.TestCase):
    def test_one_series_per_algorithm_sorted_and_only_sizes_with_a_finished_instance(self):
        s = call("fullSeries", FULL, "workingHours")
        self.assertEqual([x["algorithmId"] for x in s], ["a", "b"])
        self.assertEqual([p["x"] for p in s[1]["points"]], [10, 20])  # size 30 had nothing finish: no point

    def test_spread_is_mean_minus_plus_std_and_null_when_std_missing(self):
        b = call("fullSeries", FULL, "workingHours")[1]["points"]
        self.assertEqual((b[0]["lo"], b[0]["hi"]), (3.0, 5.0))
        self.assertIsNone(b[1]["lo"])
        self.assertIsNone(b[1]["hi"])

    def test_scale_converts_mean_and_spread(self):
        a = call("fullSeries", FULL, "totalRuntimeMs", 1000)[0]["points"][0]
        self.assertEqual((a["y"], a["lo"], a["hi"]), (0.5, 0.4995, 0.5005))

    def test_empty_when_nothing_finished(self):
        self.assertEqual(call("fullSeries", {"groups": [group("a", 5, 0, 3)]}, "days"), [])


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ComputeUnitTest(unittest.TestCase):
    def test_unit_chosen_from_largest_value(self):
        self.assertEqual(call("computeUnit", 800)["label"], "milliseconds")
        self.assertEqual(call("computeUnit", 4500)["label"], "seconds")
        self.assertEqual(call("computeUnit", 4500)["factor"], 1000)
        self.assertEqual(call("computeUnit", 180000)["label"], "minutes")
        self.assertEqual(call("computeUnit", 180000)["factor"], 60000)
        self.assertEqual(call("computeUnit", None)["label"], "milliseconds")

    def test_largest_mean_across_groups(self):
        self.assertEqual(call("maxMean", FULL["groups"], "totalRuntimeMs"), 4000)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class StoppedNotesTest(unittest.TestCase):
    def test_plain_words_per_algorithm_and_size(self):
        notes = call("stoppedNotes", FULL, {"a": "Alpha"})
        self.assertEqual(notes, [
            "Not plotted: Alpha had 1 example that did not finish at 10 places. The line there averages the 2 that finished.",
            "Not plotted: b had 2 examples that did not finish at 20 places. The line there uses the 1 that finished.",
            "Not plotted: b had 3 examples that did not finish at 30 places. No example finished, so there is no point."])

    def test_nothing_stopped_gives_no_notes(self):
        self.assertEqual(call("stoppedNotes", {"groups": [group("a", 5, 3, 0, 1, 0, 1)]}, {}), [])


if __name__ == "__main__":
    unittest.main()
