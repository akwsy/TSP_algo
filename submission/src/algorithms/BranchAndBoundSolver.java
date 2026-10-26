package algorithms;

import graph.*;
import java.util.*;
import static algorithms.RouteResult.Status.*;

/** Exact subset-and-order search: maximize visits, then minimize total distance. */
public final class BranchAndBoundSolver implements RouteSolver {
    @Override public RouteResult solve(DestinationGraph graph, double startTime, double timePeriod, SolverOptions options) {
        long started = System.nanoTime();
        double deadline = ScheduleEvaluator.deadline(graph, startTime, timePeriod);
        Search search = new Search(graph, startTime, timePeriod, deadline, options, started);
        if (graph.size() > options.maxDestinations())
            return GreedyInsertionSolver.result(SEARCH_LIMIT_REACHED, search.best, started, 0,
                    "Destination cap exceeded; returning the feasible depot-only route");
        long remaining = Math.max(0, options.timeLimitMillis() - (System.nanoTime() - started) / 1_000_000);
        RouteResult greedy = new GreedyInsertionSolver().solve(graph, startTime, timePeriod,
                new SolverOptions(options.maxDestinations(), remaining));
        if (greedy.hasRoute()) search.best = greedy.schedule();
        search.dfs(0, startTime, 0);
        return GreedyInsertionSolver.result(search.timedOut ? SEARCH_LIMIT_REACHED : OPTIMAL,
                search.best, started, search.states, search.timedOut
                ? "Computation limit reached; returning best subset found, without an optimality proof"
                : "Exact search completed: maximum visits, then minimum distance");
    }

    private static final class Search {
        final DestinationGraph g;
        final double start, period, deadline;
        final SolverOptions options;
        final long started;
        final boolean[] used;
        final List<Integer> path = new ArrayList<>(List.of(0));
        ScheduleEvaluator.Schedule best;
        long states;
        boolean timedOut;
        Search(DestinationGraph g, double start, double period, double deadline, SolverOptions options, long started) {
            this.g = g; this.start = start; this.period = period; this.deadline = deadline;
            this.options = options; this.started = started;
            used = new boolean[g.size()]; used[0] = true;
            best = ScheduleEvaluator.evaluate(g, List.of(0, 0), start, period).schedule();
        }
        void dfs(int current, double time, double distance) {
            if (options.expired(started)) { timedOut = true; return; }
            states++;
            // Every prefix is a candidate answer: skipped customers are permitted.
            int count = path.size() - 1, bestCount = best.route().size() - 2;
            double closedDistance = distance + g.distance(current, 0);
            if (count > bestCount || (count == bestCount && closedDistance < best.distanceKm())) {
                List<Integer> closed = new ArrayList<>(path); closed.add(0);
                best = ScheduleEvaluator.evaluate(g, closed, start, period).schedule();
                bestCount = count;
            }
            List<Integer> next = new ArrayList<>();
            for (int v = 1; v < g.size(); v++) if (!used[v]) {
                double visit = Math.max(time + g.travelMinutes(current, v), g.destination(v).opensAt());
                // Direct travel is optimistic under the metric, constant-speed model.
                // Exclude an unreachable customer, not the entire branch.
                if (visit <= g.destination(v).closesAt() + ScheduleEvaluator.EPS
                        && visit + g.travelMinutes(v, 0) <= deadline + ScheduleEvaluator.EPS) next.add(v);
            }
            int upperCount = count + next.size();
            if (upperCount < bestCount) return;
            // Direct return is a lower bound for the distance of any extension.
            if (upperCount == bestCount && closedDistance > best.distanceKm() + ScheduleEvaluator.EPS) return;
            next.sort(Comparator.comparingDouble((Integer v) -> g.destination(v).closesAt())
                    .thenComparingDouble(v -> g.distance(current, v))
                    .thenComparingLong(v -> g.destination(v).geoNameId()));
            for (int v : next) {
                double visit = Math.max(time + g.travelMinutes(current, v), g.destination(v).opensAt());
                used[v] = true; path.add(v);
                dfs(v, visit, distance + g.distance(current, v));
                path.remove(path.size() - 1); used[v] = false;
                if (timedOut) return;
            }
        }
    }
}
