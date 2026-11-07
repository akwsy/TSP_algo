"""Loading full-run sessions in the browser modules, run under node with a stubbed fetch."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

LIB = Path(__file__).resolve().parent.parent / "site" / "js" / "lib"


def run_node(body, files):
    """Run `body` (async JS) with fetch serving `files` ({url: json}); other URLs answer 404.
    Prints {"result": ..., "fetched": [urls]}."""
    script = f"""
const files = {json.dumps(files)};
const fetched = [];
globalThis.fetch = async (url) => {{
  fetched.push(url);
  if (!(url in files)) return {{ ok: false, status: 404, json: async () => ({{}}) }};
  return {{ ok: true, status: 200, json: async () => files[url] }};
}};
const lib = (name) => import({json.dumps(LIB.as_uri())} + "/" + name);
const result = await (async () => {{ {body} }})();
console.log(JSON.stringify({{ result, fetched }}));
"""
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    if out.returncode:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


def entry(name, **extra):
    return {"file": f"sessions/{name}.json", "algorithmId": "a", "instanceId": "n5-seed1", "outcome": "did not finish",
            "timestamp": "2026-01-01T00:00:00+00:00", **extra}


DETAILS = {"commit": "abc", "totalDistanceKm": 12.5, "explanation": "Stopped on day 2: the algorithm crashed (x)"}
INDEX = "/results/sessions-index.json"


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SessionIndexOnlyTest(unittest.TestCase):
    def test_pages_get_commit_distance_and_explanation_from_the_index_without_fetching_session_files(self):
        files = {INDEX: {"sessions": [entry("one", **DETAILS), entry("two", **{**DETAILS, "commit": None})]}}
        out = run_node('return await (await lib("sessions.js")).loadSessions();', files)
        self.assertEqual([(s["commit"], s["totalDistanceKm"], s["explanation"]) for s in out["result"]],
                         [("abc", 12.5, DETAILS["explanation"]), (None, 12.5, DETAILS["explanation"])])
        self.assertEqual(out["fetched"], [INDEX])

    def test_an_old_entry_without_the_fields_falls_back_to_its_session_file(self):
        files = {INDEX: {"sessions": [entry("old"), entry("new", **DETAILS)]},
                 "/results/sessions/old.json": {"commit": "zzz", "totalDistanceKm": 3, "explanation": "E"}}
        out = run_node('return await (await lib("sessions.js")).loadSessions();', files)
        old, new = out["result"]
        self.assertEqual((old["commit"], old["totalDistanceKm"], old["explanation"]), ("zzz", 3, "E"))
        self.assertEqual(new["commit"], "abc")
        self.assertEqual(out["fetched"], [INDEX, "/results/sessions/old.json"])

    def test_an_unreadable_old_session_file_leaves_the_entry_as_it_is(self):
        files = {INDEX: {"sessions": [entry("old")]}}
        out = run_node('return await (await lib("sessions.js")).loadSessions();', files)
        self.assertEqual(out["result"], [entry("old")])

    def test_no_index_means_no_sessions(self):
        out = run_node('return await (await lib("sessions.js")).loadSessions();', {})
        self.assertEqual(out["result"], [])


if __name__ == "__main__":
    unittest.main()
