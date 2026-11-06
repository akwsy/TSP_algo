"""Route detail dropdown logic (site/js/lib/runpicker.js), run under node. Expected values are hand-worked."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

MODEL = Path(__file__).resolve().parent.parent / "site" / "js" / "lib" / "runpicker.js"


def call(fn, *args):
    script = (f"import * as m from {json.dumps(MODEL.as_uri())};"
              f"console.log(JSON.stringify(m[{json.dumps(fn)}](...{json.dumps(list(args))})));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def run(alg, seed, n, ts="2026-01-01T00:00:00", file=None):
    return {"file": file or f"{alg}-{n}-{seed}-{ts}", "algorithmId": alg, "seed": seed, "numCustomers": n, "timestamp": ts}


RUNS = [run("a", 1, 5), run("a", 2, 5), run("a", 1, 10), run("a", 2, 10), run("a", 3, 10),
        run("b", 1, 5), run("b", 4, 15)]


@unittest.skipUnless(shutil.which("node"), "node not installed")
class RunPickerTest(unittest.TestCase):
    def test_lists_only_options_that_exist_for_the_choice(self):
        s = call("pickerState", RUNS, {"algorithmId": "a", "seed": 1, "numCustomers": 10})
        self.assertEqual(s["algorithms"], ["a", "b"])
        self.assertEqual(s["sizes"], [5, 10])
        self.assertEqual(s["seeds"], [1, 2, 3])
        self.assertEqual(s["file"], "a-10-1-2026-01-01T00:00:00")
        self.assertFalse(s["adjusted"])

    def test_changing_algorithm_keeps_other_choices_when_valid_else_nearest(self):
        s = call("pickerState", RUNS, {"algorithmId": "b", "seed": 1, "numCustomers": 10})
        self.assertEqual((s["sizes"], s["selected"]["numCustomers"]), ([5, 15], 5))
        self.assertEqual(s["selected"]["seed"], 1)
        self.assertTrue(s["adjusted"])
        s = call("pickerState", RUNS, {"algorithmId": "b", "seed": 1, "numCustomers": 5})
        self.assertFalse(s["adjusted"])

    def test_seed_falls_back_to_nearest_available(self):
        s = call("pickerState", RUNS, {"algorithmId": "b", "seed": 2, "numCustomers": 15})
        self.assertEqual(s["selected"]["seed"], 4)
        s = call("pickerState", RUNS, {"algorithmId": "a", "seed": 9, "numCustomers": 10})
        self.assertEqual(s["selected"]["seed"], 3)

    def test_latest_run_wins_for_a_combination(self):
        runs = RUNS + [run("a", 1, 10, "2026-02-01T00:00:00", "newer")]
        self.assertEqual(call("pickerState", runs, {"algorithmId": "a", "seed": 1, "numCustomers": 10})["file"], "newer")

    def test_old_file_link_resolves_to_its_choice(self):
        self.assertEqual(call("choiceFromFile", RUNS, "b-15-4-2026-01-01T00:00:00"),
                         {"algorithmId": "b", "seed": 4, "numCustomers": 15})
        self.assertIsNone(call("choiceFromFile", RUNS, "nope"))

    def test_empty_or_missing_choice_picks_first_and_no_runs_gives_no_file(self):
        self.assertEqual(call("pickerState", RUNS, {})["selected"], {"algorithmId": "a", "seed": 1, "numCustomers": 5})
        self.assertIsNone(call("pickerState", [], {})["file"])


if __name__ == "__main__":
    unittest.main()
