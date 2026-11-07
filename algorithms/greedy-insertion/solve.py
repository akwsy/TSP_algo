"""Greedy insertion, original version (O(n^4)): JSON instance on stdin, JSON result on stdout.

A Python port of the team's earlier GreedyInsertionSolver.java. Kept as the reference that
greedy-insertion-cached is compared against; it is deliberately not registered with the
harness (no algorithm.json), see README.md in this folder.

Each round tries every unvisited customer in every gap of the current route. For every try
it copies the route, inserts the customer and replays the whole schedule from the depot to
check the time windows and the deadline. Among the feasible tries it keeps the one that adds
the least distance; ties go to the earlier closing time, then the lower GeoNames id, then the
earlier position. It stops when no try is feasible.
"""
import json
import sys

EPS = 1e-9


def feasible(inst, route):
    """Replay `route` exactly as the harness does (spec section 7). O(len(route)).
    Returns (is_feasible, number of legs replayed)."""
    locs = inst["locations"]
    dist = inst["distanceKm"]
    speed = inst["speedKmh"]
    clock = inst["departureMinute"]
    legs = 0
    for i, j in zip(route, route[1:]):
        legs += 1
        arrive = clock + dist[i][j] / speed * 60
        if j == 0:
            return arrive <= inst["deadlineMinute"] + EPS, legs
        start = max(arrive, locs[j]["opensAt"])
        if start > locs[j]["closesAt"] + EPS:
            return False, legs
        clock = start
    return True, legs


def solve(inst):
    locs = inst["locations"]
    dist = inst["distanceKm"]
    n = len(locs)

    route = [0, 0]
    used = [False] * n
    used[0] = True
    tries = 0  # (customer, gap) pairs evaluated
    legs = 0   # schedule legs replayed across all tries: the real cost of the checks
    while len(route) < n + 1:
        best_key = best_route = best_v = None
        for v in range(1, n):
            if used[v]:
                continue
            for pos in range(1, len(route)):
                candidate = route[:pos] + [v] + route[pos:]   # O(k) copy
                tries += 1
                ok, replayed = feasible(inst, candidate)      # O(k) replay
                legs += replayed
                if not ok:
                    continue
                a, b = route[pos - 1], route[pos]
                delta = dist[a][v] + dist[v][b] - dist[a][b]
                key = (delta, locs[v]["closesAt"], locs[v]["geonameId"], pos)
                if best_key is None or key < best_key:
                    best_key, best_route, best_v = key, candidate, v
        if best_key is None:
            break
        route = best_route
        used[best_v] = True
    return {"route": route, "status": "HEURISTIC",
            "notes": "greedy insertion, full replay per try",
            "stats": {"iterations": tries, "legsReplayed": legs}}


if __name__ == "__main__":
    json.dump(solve(json.load(sys.stdin)), sys.stdout)
    sys.stdout.write("\n")
