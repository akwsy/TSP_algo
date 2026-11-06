"""The worked example in docs/ALGORITHM_SPEC.md must be real.

Its input must be what the graph builder produces, its output what the baseline
prints, and every number it states must match the validator.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from harness.config import InstanceConfig  # noqa: E402
from harness.dataset import load_places  # noqa: E402
from harness.instance import build_instance  # noqa: E402
from harness.validator import validate_route  # noqa: E402

SPEC = ROOT / "docs" / "ALGORITHM_SPEC.md"
BASELINE = ROOT / "algorithms" / "nearest-neighbour"
EXAMPLE_SEED, EXAMPLE_CUSTOMERS = 5, 4


def section(text, name):
    match = re.search(rf"<!-- example:{name} -->(.*?)<!-- /example:{name} -->", text, re.S)
    if not match:
        raise AssertionError(f"marker example:{name} not found in {SPEC.name}")
    return match.group(1)


def json_block(text, name):
    body = re.search(r"```json\n(.*?)```", section(text, name), re.S)
    return json.loads(body.group(1))


def table_rows(text, name):
    rows = []
    for line in section(text, name).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0].isdigit():
            rows.append(cells)
    return rows


class WorkedExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SPEC.read_text(encoding="utf-8")
        cls.instance = json_block(cls.text, "input")

    def test_input_is_what_the_graph_builder_produces(self):
        real = build_instance(load_places(ROOT / "data" / "MY.txt"),
                              InstanceConfig(seed=EXAMPLE_SEED, num_customers=EXAMPLE_CUSTOMERS))
        self.assertEqual(self.instance, real)

    def test_output_is_what_the_baseline_prints(self):
        meta = json.loads((BASELINE / "algorithm.json").read_text())
        proc = subprocess.run(meta["command"], cwd=BASELINE, input=json.dumps(self.instance),
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), json_block(self.text, "output"))

    def test_scores_match_the_validator(self):
        route = json_block(self.text, "output")["route"]
        real = validate_route(self.instance, route)
        stated = json_block(self.text, "result")
        for key, value in stated.items():
            got = real[key]
            if isinstance(value, float):
                got = round(got, 2)
            self.assertEqual(got, value, key)

    def test_schedule_table_matches_the_validator(self):
        route = json_block(self.text, "output")["route"]
        schedule = validate_route(self.instance, route)["schedule"]
        rows = table_rows(self.text, "schedule")
        # Columns: id | name | window | arrive | wait | start = leave
        self.assertEqual([int(r[0]) for r in rows], [s["id"] for s in schedule])
        for row, stop in zip(rows, schedule):
            self.assertEqual(float(row[3]), round(stop["arriveMinute"], 2), row)
            self.assertEqual(float(row[4]), round(stop["startMinute"] - stop["arriveMinute"], 2), row)
            self.assertEqual(float(row[5]), round(stop["leaveMinute"], 2), row)


if __name__ == "__main__":
    unittest.main()
