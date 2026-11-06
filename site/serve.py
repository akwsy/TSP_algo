"""Serve the website: python3 site/serve.py [--results DIR] [--algorithms DIR] [--port 8000]

  /                 the static site (this folder)
  /results/...      the results folder (default: ./results; use --results to point elsewhere,
                    e.g. tests/fixtures/sample-results)
  /api/algorithms   each algorithm.json under the algorithms folder, as a JSON list
Standard library only; no network access needed.
"""
import argparse
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read_algorithms(folder):
    out = []
    for path in sorted(Path(folder).glob("*/algorithm.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, results, algorithms, **kw):
        self.results, self.algorithms = Path(results), Path(algorithms)
        super().__init__(*args, directory=str(HERE), **kw)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/results/"):
            rel = Path(*[p for p in clean[len("/results/"):].split("/") if p not in ("", ".", "..")]) \
                if clean != "/results/" else Path("index.json")
            return str(self.results / rel)
        return super().translate_path(path)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/algorithms":
            body = json.dumps(read_algorithms(self.algorithms)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def make_server(port=8000, results=ROOT / "results", algorithms=ROOT / "algorithms", host="127.0.0.1"):
    return ThreadingHTTPServer((host, port), partial(Handler, results=results, algorithms=algorithms))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Serve the results website.")
    ap.add_argument("--results", default=str(ROOT / "results"), help="results folder")
    ap.add_argument("--algorithms", default=str(ROOT / "algorithms"), help="algorithms folder")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    server = make_server(args.port, args.results, args.algorithms)
    print(f"Serving http://127.0.0.1:{server.server_port}/  (results: {args.results})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
