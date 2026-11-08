"""Website: loads the sample results and renders every view in headless Chrome without console errors.

Skips when node or Chrome is missing (then this is only covered by a manual check). Run by hand with screenshots:
node tests/site_smoke.mjs http://127.0.0.1:PORT --matrix --shots DIR
"""
import json
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "site"))
import serve  # noqa: E402

CHROME = [Path(p) for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser")]


@unittest.skipUnless(shutil.which("node") and any(c.exists() for c in CHROME), "needs node and Chrome")
class SitePagesTest(unittest.TestCase):
    def test_every_view_renders_without_console_errors(self):
        server = serve.make_server(0, FIX / "sample-results", FIX / "sample-algorithms", instances=FIX / "sample-instances")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        out = subprocess.run(["node", str(ROOT / "tests" / "site_smoke.mjs"), f"http://127.0.0.1:{server.server_port}", "--wait", "3000"],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        pages = json.loads(out.stdout)
        self.assertEqual(len(pages), 14)  # seven pages, each in both toggle states
        self.assertEqual({p["view"] for p in pages}, {"first", "full"})
        for p in pages:
            self.assertEqual(p["errors"], [], f"{p['page']} ({p['view']})")

    def test_compare_page_on_the_suite_fixture(self):
        """The Compare page on a real experiment series (tests/fixtures/sample-suite, trimmed from a full suite run): every
        section, one chart per experiment plus the trade-off, a selected grid cell and links to examples on the map."""
        server = serve.make_server(0, FIX / "sample-suite", ROOT / "algorithms", instances=FIX / "sample-instances")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        out = subprocess.run(["node", str(ROOT / "tests" / "site_smoke.mjs"), f"http://127.0.0.1:{server.server_port}", "--wait", "3000",
                              "--pages", "compare", "--matrix"], capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        pages = json.loads(out.stdout)
        self.assertEqual(len(pages), 8)  # desktop and phone, light and dark, both toggle states
        for p in pages:
            self.assertEqual(p["errors"], [], f"{p['device']} {p['scheme']} ({p['view']})")

    def test_map_fullscreen_fills_the_viewport_and_escape_restores(self):
        """Regression: an ancestor's entrance animation (transform) became the containing block of the position:fixed overlay,
        so Fullscreen showed a clipped, collapsed map. Leaflet and SVG, desktop and phone, Fullscreen API and CSS fallback."""
        server = serve.make_server(0, FIX / "sample-results", FIX / "sample-algorithms", instances=FIX / "sample-instances")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        out = subprocess.run(["node", str(ROOT / "tests" / "site_fullscreen.mjs"), f"http://127.0.0.1:{server.server_port}"],
                             capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
