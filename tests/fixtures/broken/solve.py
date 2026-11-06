"""Deliberately broken algorithm for runner tests. Mode comes from argv[1]."""
import json
import sys
import time

mode = sys.argv[1]
json.load(sys.stdin)
if mode == "infeasible":
    print(json.dumps({"route": [0, 1, 1, 0], "status": "HEURISTIC"}))
elif mode == "malformed":
    print("{not json")
elif mode == "bad-status":
    print(json.dumps({"route": [0, 0], "status": "SUPERB"}))
elif mode == "bad-types":
    print(json.dumps({"route": "0,1,0", "status": 7, "stats": [1]}))
elif mode == "crash":
    sys.stderr.write("boom: something went wrong\n")
    sys.exit(3)
elif mode == "sleep":
    time.sleep(30)
elif mode == "partial":
    print(json.dumps({"route": [0, 0], "status": "HEURISTIC"}), flush=True)
    time.sleep(30)
