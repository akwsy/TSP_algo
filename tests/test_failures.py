"""Runner failure handling, through the CLI, using a deliberately broken fixture algorithm."""
import json
import sys
import unittest

import test_run

ROOT = test_run.ROOT

BROKEN = ROOT / "tests" / "fixtures" / "broken" / "solve.py"
MODES = ("infeasible", "malformed", "bad-status", "bad-types", "crash", "sleep", "partial")


class FailureTest(test_run.CliCase):
    def setUp(self):
        super().setUp()
        for mode in MODES:
            folder = self.algs / mode
            folder.mkdir()
            (folder / "algorithm.json").write_text(json.dumps({
                "id": mode, "displayName": mode, "timeLimitSeconds": 1,
                "command": [sys.executable, str(BROKEN), mode]}))
        self.run_cli("--seeds", "1")

    def rec(self, mode):
        return self.record(self.entry(mode, 1))

    def assertFailure(self, mode, text):
        rec = self.rec(mode)
        self.assertFalse(rec["valid"])
        self.assertIn(text, rec["failureReason"])
        self.assertIsNone(rec["visited"])
        self.assertIsNone(rec["distanceKm"])
        return rec

    def test_infeasible_route_has_specific_reason(self):
        rec = self.assertFailure("infeasible", "repeats a customer")
        self.assertEqual(rec["route"], [0, 1, 1, 0])

    def test_malformed_json(self):
        rec = self.assertFailure("malformed", "not valid JSON")
        self.assertIsNone(rec["route"])

    def test_unknown_status(self):
        self.assertFailure("bad-status", "unknown status 'SUPERB'")

    def test_wrong_typed_fields(self):
        self.assertFailure("bad-types", "status must be a string")

    def test_crash_records_exit_code_and_stderr(self):
        rec = self.assertFailure("crash", "exited with code 3")
        self.assertIn("boom: something went wrong", rec["stderr"])
        self.assertIsNone(rec["route"])

    def test_overrun_is_killed_and_recorded_as_time_limit(self):
        rec = self.assertFailure("sleep", "time limit")
        self.assertEqual(rec["status"], "TIME_LIMIT")
        self.assertIsNone(rec["route"])
        self.assertLess(rec["runtimeMs"], 5000)

    def test_overrun_keeps_route_printed_before_the_kill(self):
        rec = self.rec("partial")
        self.assertEqual((rec["status"], rec["route"], rec["valid"], rec["visited"]),
                         ("TIME_LIMIT", [0, 0], True, 0))

    def test_good_runs_have_empty_stderr_and_fixture_is_not_a_real_entry(self):
        self.assertEqual(self.rec("skip-all")["stderr"], "")
        real = {p.parent.name for p in (ROOT / "algorithms").glob("*/algorithm.json")}
        self.assertNotIn("broken", real)
        self.assertFalse(list((ROOT / "algorithms").glob("*/broken*")))


if __name__ == "__main__":
    unittest.main()
