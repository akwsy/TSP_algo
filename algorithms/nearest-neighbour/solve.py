"""Nearest neighbour baseline: JSON instance on stdin, JSON result on stdout."""
import json
import sys

EPS = 1e-9


def solve(inst):
    locs = inst["locations"]
    dist = inst["distanceKm"]
    speed = inst["speedKmh"]
    deadline = inst["deadlineMinute"]

    def minutes(i, j):
        return dist[i][j] / speed * 60

    route = [0]
    clock = inst["departureMinute"]
    here = 0
    todo = set(range(1, len(locs)))
    while True:
        best = None  # (distance, id, start time)
        for j in sorted(todo):
            start = max(clock + minutes(here, j), locs[j]["opensAt"])
            if start > locs[j]["closesAt"] + EPS:
                continue
            if start + minutes(j, 0) > deadline + EPS:
                continue
            if best is None or dist[here][j] < best[0]:
                best = (dist[here][j], j, start)
        if best is None:
            break
        _, here, clock = best
        todo.discard(here)
        route.append(here)
    route.append(0)
    return {"route": route, "status": "HEURISTIC",
            "notes": "nearest-neighbour baseline",
            "stats": {"customersVisited": len(route) - 2}}


if __name__ == "__main__":
    json.dump(solve(json.load(sys.stdin)), sys.stdout)
    sys.stdout.write("\n")
