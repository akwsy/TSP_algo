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
  if (files[url] === null) throw new TypeError("network down");
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


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SharedLoadersTest(unittest.TestCase):
    """One cached sessions-index loader and one cached session-file loader (lib/data.js) for every page."""

    def test_index_loader_returns_entries_and_is_cached(self):
        files = {INDEX: {"sessions": [entry("one")]}}
        out = run_node('const d = await lib("data.js"); return [await d.loadSessionsIndex(), await d.loadSessionsIndex()];', files)
        self.assertEqual(out["result"], [[entry("one")], [entry("one")]])
        self.assertEqual(out["fetched"], [INDEX])

    def test_index_loader_never_throws_missing_malformed_or_unreachable_means_empty(self):
        for files in ({}, {INDEX: None}, {INDEX: {"sessions": "nope"}}, {INDEX: {}}):
            out = run_node('return await (await lib("data.js")).loadSessionsIndex();', files)
            self.assertEqual(out["result"], [], files)

    def test_session_loader_returns_the_file_and_is_cached(self):
        files = {"/results/sessions/a%20b.json": {"days": 2}}
        out = run_node('const d = await lib("data.js"); return [await d.loadSession("sessions/a b.json"), await d.loadSession("sessions/a b.json")];', files)
        self.assertEqual(out["result"], [{"days": 2}, {"days": 2}])
        self.assertEqual(out["fetched"], ["/results/sessions/a%20b.json"])

    def test_a_missing_session_file_throws_a_clear_error_callers_can_catch(self):
        out = run_node("""try { await (await lib("data.js")).loadSession("sessions/gone.json"); return "no error"; }
                          catch (e) { return e.message; }""", {})
        self.assertIn("sessions/gone.json", out["result"])
        self.assertIn("404", out["result"])

    def test_the_failures_and_history_loader_shares_the_same_index_fetch(self):
        files = {INDEX: {"sessions": [entry("one", **DETAILS)]}}
        out = run_node("""const d = await lib("data.js"); const s = await lib("sessions.js");
                          await d.loadSessionsIndex(); return (await s.loadSessions()).length;""", files)
        self.assertEqual(out["result"], 1)
        self.assertEqual(out["fetched"], [INDEX])

    def test_the_old_entry_fallback_uses_the_shared_session_loader_cache(self):
        files = {INDEX: {"sessions": [entry("old")]},
                 "/results/sessions/old.json": {"commit": "zzz", "totalDistanceKm": 3, "explanation": "E"}}
        out = run_node("""const d = await lib("data.js"); const s = await lib("sessions.js");
                          await s.loadSessions(); await d.loadSession("sessions/old.json"); return 1;""", files)
        self.assertEqual(out["fetched"], [INDEX, "/results/sessions/old.json"])


if __name__ == "__main__":
    unittest.main()
