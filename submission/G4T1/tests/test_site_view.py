"""Website view toggle and full-run Overview logic (site/js/lib/view.js and fullrun.js), run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "site" / "js" / "lib"


def call(module, fn, *args):
    script = (f"import * as m from {json.dumps((LIB / module).as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def entry(alg, rank, finished, unfinished, hours=None, km=None):
    return {"rank": rank, "algorithmId": alg, "finishedAll": unfinished == 0, "unfinished": unfinished,
            "finished": finished, "workingHours": {"mean": hours, "std": None, "n": finished},
            "totalDistanceKm": {"mean": km, "std": None, "n": finished}}


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ViewStateTest(unittest.TestCase):
    def test_default_is_first_day_and_junk_is_ignored(self):
        for stored in (None, "", "banana", 3):
            self.assertEqual(call("view.js", "resolveView", stored), "first")
        self.assertEqual(call("view.js", "resolveView", "full"), "full")
        self.assertEqual(call("view.js", "resolveView", "first"), "first")

    def test_plain_word_labels(self):
        self.assertEqual(call("view.js", "viewLabel", "first"), "First day only")
        self.assertEqual(call("view.js", "viewLabel", "full"), "Until every place is visited")

    def test_examples_per_size_wording(self):
        self.assertEqual(call("view.js", "examplesPerSizeText", 30), "30 examples per size")
        self.assertEqual(call("view.js", "examplesPerSizeText", 1), "1 example per size")
        self.assertEqual(call("view.js", "examplesPerSizeText", None), "examples per size")

    def test_arrow_keys_move_between_the_two_views(self):
        self.assertEqual(call("view.js", "viewAfterKey", "first", "ArrowRight"), "full")
        self.assertEqual(call("view.js", "viewAfterKey", "full", "ArrowRight"), "first")
        self.assertEqual(call("view.js", "viewAfterKey", "full", "ArrowLeft"), "first")
        self.assertEqual(call("view.js", "viewAfterKey", "first", "ArrowUp"), "full")
        self.assertEqual(call("view.js", "viewAfterKey", "first", "Home"), "first")
        self.assertEqual(call("view.js", "viewAfterKey", "first", "End"), "full")
        self.assertIsNone(call("view.js", "viewAfterKey", "first", "a"))

    def test_view_count_text_uses_first_day_30_and_full_from_the_data(self):
        agg = {"parameters": {"instancesPerSize": 30}, "full": {"instancesPerSize": {"5": 10, "10": 10}}}
        self.assertEqual(call("view.js", "viewCountText", "first", agg), "30 examples per size")
        self.assertEqual(call("view.js", "viewCountText", "full", agg), "10 examples per size")
        self.assertEqual(call("view.js", "viewCountText", "full", {"parameters": {}}), "not run yet")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class FullRunTest(unittest.TestCase):
    def test_stop_reasons_in_plain_words_never_raw_codes(self):
        self.assertEqual(call("fullrun.js", "reasonCountsText", {"crashed": 2, "timed_out": 1}),
                         "2 crashed, 1 ran out of time")
        self.assertEqual(call("fullrun.js", "reasonCountsText", {"no_progress": 1}),
                         "1 stopped visiting new places")
        self.assertEqual(call("fullrun.js", "reasonCountsText", {"mystery": 1}), "1 stopped for another reason")
        self.assertEqual(call("fullrun.js", "reasonCountsText", {}), "")

    def test_ranked_below_label(self):
        self.assertEqual(call("fullrun.js", "rankedBelowText", 3), "ranked below: 3 instances did not finish")
        self.assertEqual(call("fullrun.js", "rankedBelowText", 1), "ranked below: 1 instance did not finish")
        self.assertIsNone(call("fullrun.js", "rankedBelowText", 0))

    def test_finished_x_of_y(self):
        self.assertEqual(call("fullrun.js", "finishedText", 7, 10), "7 of 10")

    def test_rows_for_a_size_keep_display_order_and_attach_reasons(self):
        full = {"ranking": [{"numCustomers": 10, "instances": 4, "entries": [
            entry("good", 1, 4, 0, 5.5, 100), entry("flaky", 2, 3, 1, 9, 80), entry("dead", None, 0, 4)]}],
            "groups": [{"algorithmId": "flaky", "numCustomers": 10, "stopReasons": {"crashed": 1}, "days": {"mean": 2.0, "std": 0.5, "n": 3}},
                       {"algorithmId": "good", "numCustomers": 10, "stopReasons": {}, "days": {"mean": 1.0, "std": 0, "n": 4}},
                       {"algorithmId": "dead", "numCustomers": 10, "stopReasons": {"timed_out": 4}, "days": {"mean": None, "std": None, "n": 0}}]}
        rows = call("fullrun.js", "fullRows", full, 10)
        self.assertEqual([r["algorithmId"] for r in rows], ["good", "flaky", "dead"])
        self.assertEqual([r["rankedBelow"] for r in rows], [0, 1, 4])
        self.assertEqual(rows[1]["days"]["mean"], 2.0)
        self.assertEqual(rows[1]["reasons"], "1 crashed")
        self.assertEqual(rows[0]["reasons"], "")
        self.assertEqual(rows[2]["instances"], 4)
        self.assertEqual(call("fullrun.js", "fullRows", full, 99), [])

    def test_has_full_view_needs_a_ranking(self):
        self.assertFalse(call("fullrun.js", "hasFull", {}))
        self.assertFalse(call("fullrun.js", "hasFull", {"full": {"ranking": []}}))
        self.assertTrue(call("fullrun.js", "hasFull", {"full": {"ranking": [{"numCustomers": 5, "entries": []}]}}))

    def test_headline_figures(self):
        rows = [{"algorithmId": "good", "rank": 1, "finishedAll": True, "finished": 4, "instances": 4, "unfinished": 0},
                {"algorithmId": "flaky", "rank": 2, "finishedAll": False, "finished": 3, "instances": 4, "unfinished": 1},
                {"algorithmId": "dead", "rank": None, "finishedAll": False, "finished": 0, "instances": 4, "unfinished": 4}]
        self.assertEqual(call("fullrun.js", "fullHeadline", rows),
                         {"leaderId": "good", "compared": 3, "finishedEverything": 1, "notFinished": 5})
        self.assertEqual(call("fullrun.js", "fullHeadline", rows[2:])["leaderId"], None)


if __name__ == "__main__":
    unittest.main()
