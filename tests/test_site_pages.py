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
        self.assertEqual(len(pages), 6)
        for p in pages:
            self.assertEqual(p["errors"], [], p["page"])


if __name__ == "__main__":
    unittest.main()
