"""The site server: static pages, the results folder, and declared algorithm metadata."""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))
import serve  # noqa: E402


class ServerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.results = Path(tmp.name) / "r"
        self.results.mkdir()
        (self.results / "index.json").write_text('{"runs": []}')
        (self.results / "x.json").write_text('{"a": 1}')
        instances = Path(tmp.name) / "i"
        instances.mkdir()
        (instances / "n1-seed1.json").write_text('{"instanceId": "n1-seed1"}')
        self.server = serve.make_server(0, self.results, ROOT / "algorithms", instances=instances)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.read().decode()

    def test_serves_site_and_results_folder(self):
        self.assertIn("<html", self.get("/"))
        self.assertEqual(json.loads(self.get("/results/x.json")), {"a": 1})
        self.assertEqual(json.loads(self.get("/results/index.json")), {"runs": []})

    def test_results_path_cannot_escape_folder(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/results/../../README.md")

    def test_serves_instance_files_and_blocks_escape(self):
        self.assertEqual(json.loads(self.get("/instances/n1-seed1.json")), {"instanceId": "n1-seed1"})
        with self.assertRaises(urllib.error.HTTPError):
            self.get("/instances/../../README.md")

    def test_algorithms_endpoint_exposes_declared_complexity(self):
        algs = json.loads(self.get("/api/algorithms"))
        nn = next(a for a in algs if a["id"] == "nearest-neighbour")
        self.assertEqual(nn["complexity"]["time"], "O(n^2)")
