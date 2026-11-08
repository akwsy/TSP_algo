"""Compare page logic (site/js/lib/compare.js), run under node on the committed suite fixture and on hand-made cases.

Expected values were worked out by hand from tests/fixtures/sample-suite (suite.json and the aggregates files).
Skipped when node is missing."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "site" / "js" / "lib" / "compare.js"
SUITE = ROOT / "tests" / "fixtures" / "sample-suite"


def js(expr):
    """Evaluate `expr` with `m` (the module), `suite` and `aggs` (fixture files, by experiment name) in scope."""
    script = (f"import * as m from {json.dumps(MODULE.as_uri())};"
              "import { readFileSync } from 'node:fs';"
              f"const dir = {json.dumps(str(SUITE))};"
              "const suite = JSON.parse(readFileSync(dir + '/suite.json', 'utf8'));"
              "const aggs = Object.fromEntries(suite.experiments.map((e) => [e.name, JSON.parse(readFileSync(dir + '/' + e.aggregates, 'utf8'))]));"
              "const NAMES = {'greedy-insertion-cached': 'Greedy', 'iterated-local-search': 'ILS', 'nearest-neighbour': 'NN'};"
              f"console.log(JSON.stringify(({expr})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SweepLabelTest(unittest.TestCase):
    def test_plain_word_labels_for_every_swept_setting(self):
        self.assertEqual(js("['customers', 'period', 'period', 'speed', 'departure', 'radius'].map((p, i) => m.sweepLabel(p, [30, 480, 270, 40, 540, 50][i]))"),
                         ["30 places", "day length 8 h", "day length 4.5 h", "speed 40 km/h", "leaves at 09:00", "customers within 50 km"])

    def test_one_place_is_singular_and_unknown_parameters_still_read(self):
        self.assertEqual(js("[m.sweepLabel('customers', 1), m.sweepLabel('wind', 3), m.sweepLabel('speed', null)]"),
                         ["1 place", "wind 3", "speed n/a"])


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SeriesModelTest(unittest.TestCase):
    def test_experiments_in_suite_order_with_their_algorithms(self):
        r = js("(() => { const x = m.buildModel(suite, aggs); return [x.experiments.map((e) => e.name), x.missing, x.algorithms, x.experiments[1].values]; })()")
        self.assertEqual(r[0], ["scaling", "time-budget", "speed", "window-alignment", "spread", "stress"])
        self.assertEqual(r[1], [])
        self.assertEqual(r[2], ["greedy-insertion-cached", "iterated-local-search", "nearest-neighbour"])
        self.assertEqual(r[3], [240, 480, 720, 960, 1080])

    def test_experiments_without_results_are_listed_as_missing_and_the_rest_kept(self):
        r = js("(() => { const x = m.buildModel(suite, { ...aggs, speed: null, stress: undefined }); return [x.experiments.map((e) => e.name), x.missing]; })()")
        self.assertEqual(r, [["scaling", "time-budget", "window-alignment", "spread"], ["speed", "stress"]])

    def test_no_suite_gives_an_empty_model(self):
        self.assertEqual(js("m.buildModel(null, {})"), {"experiments": [], "missing": [], "algorithms": []})


def pair(**kw):
    base = {"sweepParam": "customers", "sweepValue": 5, "a": "a", "b": "b", "instances": 1, "excluded": 0, "aWins": 1, "bWins": 0,
            "ties": 0, "meanVisitDiff": 1.0, "visitDiffCI95": [1.0, 1.0], "meanDistanceDiffWhenEqualVisits": None,
            "meanOverlap": 0.5, "largestGaps": [{"instanceId": "n5-seed1", "aVisited": 3, "bVisited": 2, "difference": 1}]}
    base.update(kw)
    return base


@unittest.skipUnless(shutil.which("node"), "node not installed")
class HeadToHeadTest(unittest.TestCase):
    def test_cell_is_read_from_the_row_algorithms_side(self):
        c = js("m.pairCell(aggs.scaling, 30, 'iterated-local-search', 'greedy-insertion-cached')")
        self.assertEqual((c["wins"], c["ties"], c["losses"], c["examples"]), (29, 1, 0, 30))
        self.assertAlmostEqual(c["diff"], 2.1666666666666665)
        self.assertAlmostEqual(c["ci"][0], 1.6)
        self.assertAlmostEqual(c["ci"][1], 2.7333333333333334)
        self.assertEqual(c["verdict"], "more")
        self.assertAlmostEqual(c["distanceDiff"], -29.662101589573126)
        self.assertEqual(c["gaps"][0], {"instanceId": "n30-seed9", "rowVisited": 18, "colVisited": 12, "difference": 6})
        back = js("m.pairCell(aggs.scaling, 30, 'greedy-insertion-cached', 'iterated-local-search')")
        self.assertEqual((back["wins"], back["losses"], back["verdict"]), (0, 29, "fewer"))
        self.assertAlmostEqual(back["ci"][0], -2.7333333333333334)

    def test_within_the_margin_of_error_is_even_and_a_missing_pair_is_null(self):
        c = js("m.pairCell(aggs['window-alignment'], 360, 'greedy-insertion-cached', 'iterated-local-search')")
        self.assertEqual(c["verdict"], "even")
        self.assertIsNone(js("m.pairCell(aggs.scaling, 31, 'greedy-insertion-cached', 'iterated-local-search')"))

    def test_summary_in_words_for_a_clear_lead(self):
        s = js("m.pairSummary(m.pairCell(aggs.scaling, 30, 'iterated-local-search', 'greedy-insertion-cached'), NAMES)")
        self.assertEqual(s, [
            "ILS visited on average 2.2 more places than Greedy, margin of error 1.6 to 2.7.",
            "ILS won 29 of 30 examples, tied 1 and lost none.",
            "When both visited the same number of places, ILS drove on average 29.7 km less.",
            "Their routes share 67% of the same places.",
        ])

    def test_summary_when_the_difference_could_be_chance(self):
        s = js("m.pairSummary(m.pairCell(aggs['window-alignment'], 360, 'greedy-insertion-cached', 'iterated-local-search'), NAMES)")
        self.assertEqual(s[0], "Greedy visited on average 0.1 fewer places than ILS, margin of error from 0.4 fewer to 0.1 more, so the difference may be chance.")

    def test_summary_when_places_are_always_equal(self):
        s = js("m.pairSummary(m.pairCell(aggs.spread, 25, 'greedy-insertion-cached', 'iterated-local-search'), NAMES)")
        self.assertEqual(s[0], "Greedy and ILS visited the same number of places in every example.")
        self.assertEqual(s[1], "Greedy won 2 of 30 examples, tied none and lost 28.")

    def test_summary_singular_excluded_and_missing_numbers(self):
        agg = {"pairs": [pair(excluded=1, meanOverlap=None)]}
        s = js(f"m.pairSummary(m.pairCell({json.dumps(agg)}, 5, 'a', 'b'), {{a: 'A', b: 'B'}})")
        self.assertEqual(s, ["A visited on average 1.0 more places than B, margin of error 1.0 to 1.0.",
                             "A won 1 of 1 example, tied none and lost none.",
                             "1 example was left out because one of them gave no valid answer.",
                             "Their overlap in places visited is n/a."])
        none = {"pairs": [pair(instances=0, aWins=0, meanVisitDiff=None, visitDiffCI95=None, excluded=3, largestGaps=[])]}
        s = js(f"m.pairSummary(m.pairCell({json.dumps(none)}, 5, 'a', 'b'), {{a: 'A', b: 'B'}})")
        self.assertEqual(s, ["A and B have no example where both gave a valid answer, so they cannot be compared here.",
                             "3 examples were left out because one of them gave no valid answer."])


def group(alg, value, visited, runs=30, failures=0, timeouts=0, runtime=10.0, param="customers"):
    return {"algorithmId": alg, "numCustomers": value, "sweepParam": param, "sweepValue": value, "runs": runs, "failures": failures,
            "timeouts": timeouts, "visited": {"mean": visited, "std": None, "n": runs}, "runtimeMs": {"mean": runtime, "std": None, "n": runs},
            "bestKnownRatio": {"mean": None, "n": 0}}


def tiny_suite(groups, pairs=(), name="scaling", param="customers"):
    """A one-experiment suite and its aggregates, as JS source."""
    values = sorted({g["sweepValue"] for g in groups})
    suite = {"experiments": [{"name": name, "param": param, "values": values, "aggregates": f"aggregates-{name}.json"}]}
    agg = {"experiment": name, "parameters": {"sweepParam": param, "values": values, "instancesPerSize": 30},
           "sweepValues": values, "groups": groups, "pairs": list(pairs)}
    return f"m.buildModel({json.dumps(suite)}, {{{json.dumps(name)}: {json.dumps(agg)}}})"


@unittest.skipUnless(shutil.which("node"), "node not installed")
class HeadlineTest(unittest.TestCase):
    def test_experiment_titles_are_plain_words(self):
        self.assertEqual(js("['scaling', 'time-budget', 'speed', 'window-alignment', 'spread', 'stress', 'my-test'].map((n) => m.experimentTitle(n))"),
                         ["Number of places", "Day length", "Travel speed", "Departure time", "How spread out", "Very many places", "My test"])

    def test_standings_rank_by_average_places_visited_in_each_experiment(self):
        r = js("m.standings(m.buildModel(suite, aggs))")
        self.assertEqual([(s["id"], s["avgRank"], s["firsts"]) for s in r["overall"]],
                         [("iterated-local-search", 1, 6), ("greedy-insertion-cached", 2, 0), ("nearest-neighbour", 3, 0)])
        scaling = r["byExperiment"][0]
        self.assertEqual([x["id"] for x in scaling["ranking"]], ["iterated-local-search", "greedy-insertion-cached", "nearest-neighbour"])
        self.assertAlmostEqual(scaling["ranking"][1]["mean"], 12.59, places=2)  # (4.27 + 7.13 + ... + 25.43) / 7

    def test_equal_averages_share_a_rank(self):
        r = js(f"m.standings({tiny_suite([group('a', 5, 3), group('b', 5, 3), group('c', 5, 1)])})")
        self.assertEqual([(s["id"], s["rank"]) for s in r["byExperiment"][0]["ranking"]], [("a", 1), ("b", 1), ("c", 3)])
        self.assertEqual([(s["id"], s["firsts"]) for s in r["overall"]], [("a", 1), ("b", 1), ("c", 0)])

    def test_headline_from_the_fixture(self):
        h = js("m.headline(m.buildModel(suite, aggs), NAMES, {})")
        self.assertEqual(h["leader"], "iterated-local-search")
        self.assertEqual(h["text"], "ILS visited the most places in all 6 experiments: on average 2.0 more places than Greedy and 11.6 more than NN, over 31 settings.")
        self.assertEqual(h["standing"], ["1st ILS, average rank 1.0", "2nd Greedy, average rank 2.0", "3rd NN, average rank 3.0"])
        self.assertEqual(h["caveats"], [
            "No failures or timeouts in 2,550 runs.",
            "ILS and Greedy are within the margin of error of each other at 6 of 31 settings: Departure time (3 of 5), Number of places (1 of 7), Day length (1 of 5), How spread out (1 of 5).",
        ])

    def test_caveats_name_failures_timeouts_and_inexact_algorithms(self):
        groups = [group("a", 5, 3, failures=2, timeouts=1), group("b", 5, 2, failures=1)]
        algs = {"a": {"exact": False}, "b": {"exact": False}}
        h = js(f"m.headline({tiny_suite(groups)}, {{a: 'A', b: 'B'}}, {json.dumps(algs)})")
        self.assertEqual(h["text"], "A visited the most places in the one experiment, over 1 setting.")
        self.assertEqual(h["caveats"][0], "3 of 60 runs failed (A 2, B 1) and 1 hit the time limit (A 1); they are left out of the averages.")
        self.assertIn("None of the algorithms is exact, so \"best\" means the best any of them found, not the best possible.", h["caveats"])

    def test_headline_with_no_results(self):
        self.assertEqual(js("m.headline(m.buildModel(null, {}), {}, {})"), {"leader": None, "text": "No experiment results yet.", "standing": [], "caveats": []})


if __name__ == "__main__":
    unittest.main()
