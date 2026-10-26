package evaluation.algorithms;

import algorithms.*;

import graph.*;
import java.util.*;
import static algorithms.RouteResult.Status.*;

/** Baseline: append the nearest feasible customer; never reorder earlier visits. */
public final class NearestNeighbourSolver implements RouteSolver {
    @Override public RouteResult solve(DestinationGraph graph, double startTime, double timePeriod, SolverOptions options) {
        long started = System.nanoTime(), evaluated = 0;
        double deadline = ScheduleEvaluator.deadline(graph, startTime, timePeriod);
        List<Integer> route = new ArrayList<>(List.of(0, 0));
        boolean[] used = new boolean[graph.size()]; used[0] = true;
        int current = 0; double time = startTime;
        while (route.size() < graph.size() + 1) {
            int best = -1; double bestVisit = 0;
            for (int v = 1; v < graph.size(); v++) if (!used[v]) {
                if (System.nanoTime() - started >= java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(options.timeLimitMillis())) return result(SEARCH_LIMIT_REACHED,
                        ScheduleEvaluator.evaluate(graph, route, startTime, timePeriod).schedule(), started, evaluated,
                        "Computation limit reached; returning the current feasible baseline route");
                evaluated++;
                double visit = Math.max(time + graph.travelMinutes(current, v), graph.destination(v).opensAt());
                if (visit > graph.destination(v).closesAt() + ScheduleEvaluator.EPS
                        || visit + graph.travelMinutes(v, 0) > deadline + ScheduleEvaluator.EPS) continue;
                if (best < 0 || graph.distance(current, v) < graph.distance(current, best)
                        || (Double.compare(graph.distance(current, v), graph.distance(current, best)) == 0
                            && graph.destination(v).geoNameId() < graph.destination(best).geoNameId())) {
                    best = v; bestVisit = visit;
                }
            }
            if (best < 0) break;
            route.add(route.size() - 1, best); used[best] = true;
            current = best; time = bestVisit;
        }
        return result(FEASIBLE_HEURISTIC,
                ScheduleEvaluator.evaluate(graph, route, startTime, timePeriod).schedule(), started, evaluated,
                "Nearest feasible neighbour baseline; maximum visit count is not proved");
    }
    private static RouteResult result(RouteResult.Status status, ScheduleEvaluator.Schedule schedule,
                                      long started, long states, String message) {
        return new RouteResult(status, schedule, (System.nanoTime() - started) / 1_000_000.0, states, message);
    }
}
