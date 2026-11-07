"""Behaves well on day 1 (visits customer 1 only) and misbehaves from day 2, when only one
customer is left. Mode comes from argv[1]. Meant for the 2-customer fixture instance."""
import json
import sys
import time

mode = sys.argv[1]
instance = json.load(sys.stdin)
good = json.dumps({"route": [0, 1, 0], "status": "HEURISTIC"})
if len(instance["locations"]) > 2:  # day 1
    print(good)
elif mode == "crash":
    sys.stderr.write("boom on day 2\n")
    sys.exit(3)
elif mode == "invalid-route":
    print(json.dumps({"route": [0, 1, 1, 0], "status": "HEURISTIC"}))
elif mode == "unreadable":
    print("{not json")
elif mode == "visit-nothing":
    print(json.dumps({"route": [0, 0], "status": "HEURISTIC"}))
elif mode == "valid-then-sleep":  # complete valid answer printed, then killed by the time limit
    print(good, flush=True)
    time.sleep(30)
elif mode == "no-answer-then-sleep":
    time.sleep(30)
