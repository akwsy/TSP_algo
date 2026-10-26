package algorithms;

import graph.*;
import java.util.*;

/** Shared zero-service-time scheduler. Return travel and waiting count toward the time period. */
public final class ScheduleEvaluator {
    public static final double EPS = 1e-9;
    private ScheduleEvaluator() {}

    public record Visit(int vertex, double arrival, double visitTime, double waiting) {}
    public record Schedule(List<Integer> route, List<Visit> visits, double distanceKm,
                           double travelMinutes, double waitingMinutes, double finishTime) {
        public Schedule { route = List.copyOf(route); visits = List.copyOf(visits); }
    }
    public record Evaluation(boolean feasible, Schedule schedule, String reason) {}

    public static void validateStart(DestinationGraph graph, double startTime) {
        Destination depot = graph.destination(0);
        if (!Double.isFinite(startTime) || startTime < depot.opensAt() - EPS
                || startTime > depot.closesAt() + EPS)
            throw new IllegalArgumentException("Start time is outside the depot opening window");
    }

    public static double deadline(DestinationGraph graph, double startTime, double timePeriod) {
        validateStart(graph, startTime);
        if (!Double.isFinite(timePeriod) || timePeriod < 0 || !Double.isFinite(startTime + timePeriod))
            throw new IllegalArgumentException("Time period must be finite, nonnegative and not overflow");
        return startTime + timePeriod;
    }

    /** A subset of customers is allowed, but the route must return within the period. */
    public static Evaluation evaluate(DestinationGraph graph, List<Integer> route,
                                      double startTime, double timePeriod) {
        double deadline = deadline(graph, startTime, timePeriod);
        if (route == null || route.size() < 2 || route.get(0) != 0 || route.get(route.size() - 1) != 0)
            return bad("Route must start and finish at the depot");
        boolean[] seen = new boolean[graph.size()]; seen[0] = true;
        List<Visit> visits = new ArrayList<>();
        visits.add(new Visit(0, startTime, startTime, 0));
        double time = startTime, distance = 0, travel = 0, waiting = 0;
        int previous = 0;
        for (int pos = 1; pos < route.size(); pos++) {
            int v = route.get(pos);
            if (v < 0 || v >= graph.size()) return bad("Invalid vertex");
            boolean returnLeg = pos == route.size() - 1;
            if (!returnLeg && seen[v]) return bad("Repeated destination or intermediate depot");
            seen[v] = true;
            double leg = graph.travelMinutes(previous, v);
            double arrival = time + leg;
            Destination d = graph.destination(v);
            double visitTime = returnLeg ? arrival : Math.max(arrival, d.opensAt());
            if (!returnLeg && visitTime > d.closesAt() + EPS) return bad("Late at " + d.geoNameId());
            double wait = visitTime - arrival;
            distance += graph.distance(previous, v); travel += leg; waiting += wait;
            visits.add(new Visit(v, arrival, visitTime, wait));
            time = visitTime; previous = v;
        }
        if (!Double.isFinite(time) || time > deadline + EPS) return bad("Return exceeds the time period");
        return new Evaluation(true, new Schedule(route, visits, distance, travel, waiting, time), "Feasible");
    }
    private static Evaluation bad(String reason) { return new Evaluation(false, null, reason); }
}
