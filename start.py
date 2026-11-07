"""Run every algorithm, then open the results website.

    python3 start.py                       full default run, then the site
    python3 start.py --sizes 5 10 --instances 3   a quick small run
    python3 start.py --full-run-instances 3   examples per size run until every place is visited
    python3 start.py --skip-run            just open the site on existing results
    python3 start.py --force               re-evaluate everything (both views)
    python3 start.py --rerun nearest-neighbour    re-evaluate only these algorithms

Evaluation is incremental: a run already saved in results/ for the same algorithm code
(a hash of every file in its folder), the same instance and the same time limit is reused,
not run again. Only new or changed algorithms and instances are evaluated. This holds for the
full run (until every place is visited) too; the summary says how many full-run sessions were
reused versus newly run, per algorithm.

Press Ctrl+C to stop the website.
"""
import argparse
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def wait_until_up(url, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run all algorithms, then serve the results website.")
    ap.add_argument("--sizes", type=int, nargs="+", help="numbers of places to test (default: 5 10 15 20 30 50 100)")
    ap.add_argument("--instances", type=int, help="examples per size (default: 30)")
    ap.add_argument("--full-run-instances", type=int, metavar="N",
                    help="examples per size run until every place is visited (default: 10, 0 to skip)")
    ap.add_argument("--force", action="store_true", help="re-evaluate everything, ignoring saved runs")
    ap.add_argument("--rerun", nargs="+", metavar="ID", default=[],
                    help="re-evaluate only these algorithms (by id), ignoring their saved runs")
    ap.add_argument("--skip-run", action="store_true", help="do not run the algorithms, just open the site")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    args = ap.parse_args(argv)

    if not args.skip_run:
        cmd = [sys.executable, "-m", "harness.experiment", "scaling"]
        if args.sizes:
            cmd += ["--sizes", *map(str, args.sizes)]
        if args.instances is not None:
            cmd += ["--instances", str(args.instances)]
        if args.full_run_instances is not None:
            cmd += ["--full-run-instances", str(args.full_run_instances)]
        if args.force:
            cmd.append("--force")
        if args.rerun:
            cmd += ["--rerun", *args.rerun]
        print("Evaluating the algorithms (saved runs are reused)...", flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            print("The run failed, so the website was not started.", file=sys.stderr)
            return 1

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))  # stop the website too when this script is stopped
    url = f"http://127.0.0.1:{args.port}/"
    server = subprocess.Popen([sys.executable, str(ROOT / "site" / "serve.py"), "--port", str(args.port)], cwd=ROOT)
    try:
        if wait_until_up(url):
            print(f"Website ready at {url}  (Ctrl+C to stop)", flush=True)
            if not args.no_browser:
                threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
        elif server.poll() is not None:
            print(f"The website could not start (is port {args.port} already in use? try --port).", file=sys.stderr)
            return 1
        server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait()
    return 0


if __name__ == "__main__":
    sys.exit(main())
