"""Iterated local search: JSON instance on stdin, JSON result on stdout.

The solver repeatedly destroys part of a feasible route and rebuilds it, keeping the best
route it has seen. The objective is lexicographic: maximise the number of distinct customers
visited, then minimise travelled distance.

Three ideas carry the implementation:

1. Shift, not distance. The binding constraint is the trip period, so an insertion is scored
   by how much time it pushes the rest of the schedule later, including any waiting it
   introduces. Picking the smallest added distance instead is what makes a distance-greedy
   heuristic lose visits.
2. Forward time slack. Each route position stores the largest delay it can absorb before some
   later window or the return deadline breaks (max_shift). Testing an insertion is then two
   comparisons rather than a reschedule.
3. A systematic shake. The perturbation sweeps a window of consecutive visits across the route
   and widens it only while the search is stuck. No random number generator is involved, so
   the output is byte-for-byte reproducible.

Complexity: one insertion round costs O(u * m) (u unvisited candidates, m scheduled visits),
and rebuilding the schedule after each change is O(m). An ILS iteration is a shake plus
insertion rounds until nothing fits. Total cost is O(I * u * m) per round for I iterations;
I is bounded by a stall limit and a fixed budget of candidate evaluations (not a clock), so the
program is an anytime heuristic with no polynomial bound beyond that budget. Space is O(n^2)
for the travel matrix and O(n) for the route.

Every route is replayed with the harness's own arithmetic before it is accepted as the best,
so a floating-point edge case can never make this program emit an invalid route.
"""
import json
import sys

EPS = 1e-9               # the harness's tolerance (spec section 7)
STALL_LIMIT = 4000       # iterations without a new best before the search declares convergence
RESTART_LIMIT = 150      # iterations without a new best before the walk returns to the best
MAX_CANDIDATES = 2_000_000   # deterministic work budget (insertion candidates evaluated)


class IteratedLocalSearch:
    def __init__(self, inst):
        locs = inst["locations"]
        self.dist = inst["distanceKm"]
        speed = inst["speedKmh"]
        self.depart = inst["departureMinute"]
        self.deadline = inst["deadlineMinute"]
        self.n = len(locs)

        # Same expression as the harness. O(n^2).
        n = self.n
        self.travel = [[self.dist[i][j] / speed * 60 for j in range(n)] for i in range(n)]
        self.opens = [loc["opensAt"] for loc in locs]
        self.closes = [loc["closesAt"] for loc in locs]
        self.geoname = [loc["geonameId"] for loc in locs]

        self.route = [0, 0]
        self.visited = [False] * n
        self.visited[0] = True
        self.route_distance = 0.0
        self.arrive = []
        self.visit_at = []
        self.waiting = []
        self.max_shift = []

        self.best_route = [0, 0]
        self.best_distance = 0.0

        self.candidates = 0
        self.rejected_bests = 0

        self.reschedule()

    # ------------------------------------------------------------------
    # Scheduling: one forward pass for times, one backward pass for slack
    # ------------------------------------------------------------------

    def reschedule(self):
        """Recompute arrival, visit, waiting, slack and distance for the route. O(m)."""
        route, travel, opens, closes = self.route, self.travel, self.opens, self.closes
        dist = self.dist
        k = len(route)
        last = k - 1

        arrive = [0.0] * k
        visit_at = [0.0] * k
        waiting = [0.0] * k
        arrive[0] = visit_at[0] = self.depart

        distance = 0.0
        for p in range(1, k):
            a, b = route[p - 1], route[p]
            distance += dist[a][b]
            arrive[p] = visit_at[p - 1] + travel[a][b]
            if p == last:
                # The return leg is bounded by the deadline only; no waiting at the depot.
                visit_at[p] = arrive[p]
            else:
                visit_at[p] = max(arrive[p], opens[b])
                waiting[p] = visit_at[p] - arrive[p]

        # Slack, right to left. Delaying visit_at[p] by d pushes visit_at[p+1] later by
        # max(0, d - waiting[p+1]), because waiting absorbs the first part of any delay:
        #     d <= closes[p] - visit_at[p]            (this visit still in time)
        #     d <= waiting[p+1] + max_shift[p+1]      (everything after it too)
        max_shift = [0.0] * k
        max_shift[last] = self.deadline - arrive[last]
        for p in range(last - 1, 0, -1):
            own = closes[route[p]] - visit_at[p]
            downstream = waiting[p + 1] + max_shift[p + 1]
            max_shift[p] = own if own < downstream else downstream

        self.arrive, self.visit_at = arrive, visit_at
        self.waiting, self.max_shift = waiting, max_shift
        self.route_distance = distance

    def replay_ok(self, route):
        """Full replay with the harness's arithmetic. Guards against rounding edge cases."""
        travel, opens, closes = self.travel, self.opens, self.closes
        clock = self.depart
        for i, j in zip(route, route[1:]):
            arrive = clock + travel[i][j]
            if j == 0:
                return arrive <= self.deadline + EPS
            start = max(arrive, opens[j])
            if start > closes[j] + EPS:
                return False
            clock = start
        return True

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insertion_phase(self):
        """Insert customers until none fits anywhere.

        Each round picks the globally smallest shift. With unit prizes the ratio rule
        score^2 / shift reduces to minimising the shift, without the division.
        """
        n = self.n
        travel, dist, opens, closes, geoname = (
            self.travel, self.dist, self.opens, self.closes, self.geoname)

        while True:
            route = self.route
            last = len(route) - 1
            visit_at, arrive = self.visit_at, self.arrive
            waiting, max_shift = self.waiting, self.max_shift

            best = None   # (shift, added_distance, closing, id)
            best_c = best_p = -1

            for c in range(1, n):
                if self.visited[c]:
                    continue
                closing = closes[c]
                open_c = opens[c]
                tc = travel[c]
                dc = dist[c]
                key_id = geoname[c]

                for p in range(1, last + 1):
                    self.candidates += 1
                    pred, succ = route[p - 1], route[p]

                    visit_c = visit_at[p - 1] + travel[pred][c]
                    if visit_c < open_c:
                        visit_c = open_c
                    if visit_c > closing + EPS:
                        # Visit times are non-decreasing along a route (triangle
                        # inequality), so every later gap is also too late.
                        break

                    shift = visit_c + tc[succ] - arrive[p]
                    if shift > waiting[p] + max_shift[p] + EPS:
                        continue

                    added = dist[pred][c] + dc[succ] - dist[pred][succ]
                    if best is None or self._better(shift, added, closing, key_id, best):
                        best = (shift, added, closing, key_id)
                        best_c, best_p = c, p

            if best_c < 0:
                return
            self.insert_at(best_c, best_p)

    @staticmethod
    def _better(shift, added, closing, key_id, best):
        """Smallest shift, then added distance, then closing time, then identifier.

        Earlier positions win the final tie because the scan visits them first.
        """
        b_shift, b_added, b_closing, b_id = best
        if shift < b_shift - EPS:
            return True
        if shift > b_shift + EPS:
            return False
        if added < b_added - EPS:
            return True
        if added > b_added + EPS:
            return False
        if closing < b_closing - EPS:
            return True
        if closing > b_closing + EPS:
            return False
        return key_id < b_id

    def insert_at(self, customer, position):
        self.route.insert(position, customer)
        self.visited[customer] = True
        self.reschedule()

    # ------------------------------------------------------------------
    # Shake
    # ------------------------------------------------------------------

    def shake(self, remove_count, start_slot):
        """Remove remove_count consecutive visits from start_slot, wrapping the route end."""
        m = len(self.route) - 2
        if m <= 0:
            return
        to_remove = min(remove_count, m)
        drop = {((start_slot - 1 + t) % m) + 1 for t in range(to_remove)}

        kept = [0]
        for p in range(1, m + 1):
            vertex = self.route[p]
            if p in drop:
                self.visited[vertex] = False
            else:
                kept.append(vertex)
        kept.append(0)
        self.route = kept
        self.reschedule()

    # ------------------------------------------------------------------
    # Acceptance: lexicographic on (visits, distance)
    # ------------------------------------------------------------------

    def is_better_than_best(self):
        visits, best_visits = len(self.route) - 2, len(self.best_route) - 2
        if visits != best_visits:
            return visits > best_visits
        return self.route_distance < self.best_distance - EPS

    def save_best(self):
        """Keep the route as the best, but only if the harness's arithmetic accepts it."""
        if not self.replay_ok(self.route):
            self.rejected_bests += 1
            return False
        self.best_route = list(self.route)
        self.best_distance = self.route_distance
        return True

    def restore_best(self):
        self.route = list(self.best_route)
        self.visited = [False] * self.n
        for v in self.route:
            self.visited[v] = True
        self.reschedule()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def run(self):
        self.insertion_phase()
        self.save_best()

        remove_count = 1
        start_slot = 1
        since_improve = 0
        stall = 0
        iterations = 0
        improvements = 0
        budget_hit = False

        # Nothing fits at all (or no customers): the depot-only route is the answer.
        searchable = self.n > 1 and len(self.best_route) > 2

        while searchable:
            if self.candidates >= MAX_CANDIDATES:
                budget_hit = True
                break
            if stall >= STALL_LIMIT:
                break

            iterations += 1
            self.shake(remove_count, start_slot)
            self.insertion_phase()

            if self.is_better_than_best() and self.save_best():
                improvements += 1
                remove_count = 1
                start_slot = 1
                since_improve = 0
                stall = 0
                continue

            since_improve += 1
            stall += 1

            # Advance the shake window. Once it has swept the whole route, widen it: the
            # perturbation grows more destructive only while the search is making no progress.
            slots = max(1, len(self.route) - 2)
            start_slot += remove_count
            if start_slot > slots:
                start_slot -= slots
                remove_count += 1
                # Cap the window at half the route. A tighter cap such as slots/3 silently
                # pins remove_count at 1 for any route with five or fewer visits, which
                # leaves the shake unable to do anything greedy reinsertion will not
                # immediately undo.
                cap = min(slots, max(2, slots // 2))
                if remove_count > cap:
                    remove_count = 1

            if since_improve >= RESTART_LIMIT:
                self.restore_best()
                remove_count = 1
                start_slot = 1
                since_improve = 0

        self.restore_best()
        return iterations, improvements, budget_hit


def solve(inst):
    ils = IteratedLocalSearch(inst)
    iterations, improvements, budget_hit = ils.run()
    if budget_hit:
        notes = "iterated local search stopped by its candidate budget after %d iterations" % iterations
    else:
        notes = "iterated local search converged after %d iterations" % iterations
    return {"route": [int(v) for v in ils.best_route], "status": "HEURISTIC", "notes": notes,
            "stats": {"iterations": ils.candidates, "shakeIterations": iterations,
                      "improvements": improvements, "rejectedBests": ils.rejected_bests}}


if __name__ == "__main__":
    json.dump(solve(json.load(sys.stdin)), sys.stdout)
    sys.stdout.write("\n")
