package algorithms;

import graph.*;
import java.util.*;
import static algorithms.RouteResult.Status.*;

/** Adds feasible visits until no further insertion fits the windows and period. */
public final class GreedyInsertionSolver implements RouteSolver {
    @Override public RouteResult solve(DestinationGraph graph, double startTime, double timePeriod, SolverOptions options) {
        long started = System.nanoTime(), evaluated = 0;
        ScheduleEvaluator.deadline(graph, startTime, timePeriod);
        List<Integer> route = new ArrayList<>(List.of(0, 0));
        boolean[] used = new boolean[graph.size()]; used[0] = true;
        while (route.size() < graph.size() + 1) {
            Candidate best = null;
            for (int v = 1; v < graph.size(); v++) if (!used[v]) {
                for (int pos = 1; pos < route.size(); pos++) {
                    if (options.expired(started)) return result(SEARCH_LIMIT_REACHED,
                            ScheduleEvaluator.evaluate(graph, route, startTime, timePeriod).schedule(), started, evaluated,
                            "Computation limit reached; returning the current feasible subset");
                    List<Integer> candidate = new ArrayList<>(route); candidate.add(pos, v);
                    evaluated++;
                    if (!ScheduleEvaluator.evaluate(graph, candidate, startTime, timePeriod).feasible()) continue;
                    int before = route.get(pos - 1), after = route.get(pos);
                    double delta = graph.distance(before, v) + graph.distance(v, after) - graph.distance(before, after);
                    Candidate c = new Candidate(v, pos, delta, graph.destination(v).closesAt(),
                            graph.destination(v).geoNameId(), candidate);
                    if (best == null || ORDER.compare(c, best) < 0) best = c;
                }
            }
            if (best == null) break;
            route = best.route(); used[best.vertex()] = true;
        }
        return result(FEASIBLE_HEURISTIC,
                ScheduleEvaluator.evaluate(graph, route, startTime, timePeriod).schedule(), started, evaluated,
                "Feasible subset; maximum visit count is not proved");
    }
    private record Candidate(int vertex, int position, double delta, double close, long id, List<Integer> route) {}
    private static final Comparator<Candidate> ORDER = Comparator.comparingDouble(Candidate::delta)
            .thenComparingDouble(Candidate::close).thenComparingLong(Candidate::id)
            .thenComparingInt(Candidate::position);
    static RouteResult result(RouteResult.Status status, ScheduleEvaluator.Schedule schedule,
                              long started, long states, String message) {
        return new RouteResult(status, schedule, (System.nanoTime() - started) / 1_000_000.0, states, message);
    }
}
