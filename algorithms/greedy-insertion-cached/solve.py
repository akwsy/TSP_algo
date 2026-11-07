"""Greedy insertion with cache (O(n^3)): JSON instance on stdin, JSON result on stdout.

Same greedy rule as the original greedy insertion (algorithms/greedy-insertion): each round,
insert the feasible (customer, gap) pair that adds the least distance; ties go to the earlier
closing time, then the lower GeoNames id, then the earlier position. Stop when nothing fits.

What changes is the feasibility check. Instead of copying the route and replaying the whole
schedule for every try (O(k)), two arrays are rebuilt once per round (O(k)):

  leave[p]  - earliest time we can leave the stop at position p   (forward pass)
  latest[p] - latest time we may start at position p and still keep every later window
              and the deadline                                    (backward pass)
              latest[end] = deadline
              latest[p]   = min(closesAt[p], latest[p+1] - travel(p, p+1))

Inserting v between positions p-1 (stop a) and p (stop b) is then checked in O(1):

  start_v = max(leave[p-1] + travel(a, v), opensAt[v])
  fits    = start_v <= closesAt[v]  and  start_v + travel(v, b) <= latest[p]

This is exact (not an approximation) because service time is zero and waiting is allowed:
stops before a are unchanged, and inserting v can only delay later stops, which latest[p]
already accounts for.

Two further details:
- Pruning: a customer that fits in no gap this round can never fit later (a longer route is
  only tighter, by the triangle inequality), so it is dropped for good.
- Boundary guard: when the O(1) check is within GUARD minutes of the boundary, the candidate
  is replayed in full with the harness's exact arithmetic, so floating-point rounding can
  never make this program accept a route the harness would reject. This almost never runs.
"""
import json
import sys

EPS = 1e-9      # the harness's tolerance (spec section 7)
GUARD = 1e-6    # margin below which the O(1) check defers to a full replay


def solve(inst):
    locs = inst["locations"]
    dist = inst["distanceKm"]
    speed = inst["speedKmh"]
    depart = inst["departureMinute"]
    deadline = inst["deadlineMinute"]
    n = len(locs)

    # Travel minutes, computed once with the same expression as the harness. O(n^2).
    travel = [[dist[i][j] / speed * 60 for j in range(n)] for i in range(n)]
    opens = [loc["opensAt"] for loc in locs]
    closes = [loc["closesAt"] for loc in locs]
    geoname = [loc["geonameId"] for loc in locs]

    def replay(route):
        """Full replay exactly as the harness does it; only used near the boundary."""
        clock = depart
        for i, j in zip(route, route[1:]):
            arrive = clock + travel[i][j]
            if j == 0:
                return arrive <= deadline + EPS
            start = max(arrive, opens[j])
            if start > closes[j] + EPS:
                return False
            clock = start
        return True

    route = [0, 0]
    alive = list(range(1, n))   # customers that may still fit somewhere
    tries = replays = pruned = 0

    while alive:
        k = len(route)

        # Rebuild the cache for the current route. O(k).
        leave = [0.0] * k
        leave[0] = depart
        for p in range(1, k - 1):
            leave[p] = max(leave[p - 1] + travel[route[p - 1]][route[p]], opens[route[p]])
        latest = [0.0] * k
        latest[k - 1] = deadline
        for p in range(k - 2, 0, -1):
            latest[p] = min(closes[route[p]], latest[p + 1] - travel[route[p]][route[p + 1]])

        best_key = None
        still_alive = []
        for v in alive:                               # O(n)
            fits_somewhere = False
            for p in range(1, k):                     # O(k) gaps
                a, b = route[p - 1], route[p]
                tries += 1
                start_v = max(leave[p - 1] + travel[a][v], opens[v])
                margin = min(closes[v] - start_v, latest[p] - (start_v + travel[v][b]))
                if margin < -GUARD:
                    continue
                if margin <= GUARD:
                    replays += 1
                    if not replay(route[:p] + [v] + route[p:]):
                        continue
                fits_somewhere = True
                delta = dist[a][v] + dist[v][b] - dist[a][b]
                key = (delta, closes[v], geoname[v], p, v)
                if best_key is None or key < best_key:
                    best_key = key
            if fits_somewhere:
                still_alive.append(v)
            else:
                pruned += 1

        if best_key is None:
            break
        p, v = best_key[3], best_key[4]
        route.insert(p, v)                            # O(k)
        alive = [u for u in still_alive if u != v]

    return {"route": route, "status": "HEURISTIC",
            "notes": "greedy insertion with leave/latest cache",
            "stats": {"iterations": tries, "boundaryReplays": replays,
                      "customersPruned": pruned}}


if __name__ == "__main__":
    json.dump(solve(json.load(sys.stdin)), sys.stdout)
    sys.stdout.write("\n")
