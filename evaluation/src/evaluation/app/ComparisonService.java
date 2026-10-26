package evaluation.app;

import algorithms.*;
import app.ScenarioFiles;
import evaluation.algorithms.NearestNeighbourSolver;
import graph.*;
import java.util.*;

/** One shared Java comparison contract for the browser and integration tests. */
public final class ComparisonService {
    private ComparisonService() {}
    public static Map<String, Object> scenario(ScenarioFiles.Scenario scenario) {
        DestinationGraph graph = scenario.graph();
        List<Object> locations = new ArrayList<>();
        for (int i = 0; i < graph.size(); i++) {
            Destination d = graph.destination(i);
            locations.add(Map.of("index", i, "id", d.geoNameId(), "name", d.name(), "latitude", d.latitude(),
                    "longitude", d.longitude(), "opensAt", d.opensAt(), "closesAt", d.closesAt()));
        }
        // Send the actual Java graph distances so hover inspection never approximates a second graph.
        List<Object> distances = new ArrayList<>();
        for (int from = 0; from < graph.size(); from++) {
            List<Double> row = new ArrayList<>();
            for (int to = 0; to < graph.size(); to++) row.add(graph.distance(from, to));
            distances.add(row);
        }
        return Map.of("distanceKm", distances, "destinations", locations, "clockStartMinutes", scenario.clockStartMinutes(),
                "speedKmh", scenario.speedKmh(), "durationMinutes", scenario.durationMinutes(),
                "customerCount", graph.size() - 1, "edgeCount", (long)graph.size() * (graph.size() - 1) / 2);
    }
    public static Map<String, Object> compare(ScenarioFiles.Scenario scenario, double start, double period, SolverOptions options) {
        ScheduleEvaluator.deadline(scenario.graph(), start, period);
        List<Object> results = new ArrayList<>();
        results.add(result("nearest", "Nearest neighbour", true, new NearestNeighbourSolver(), scenario.graph(), start, period, options));
        results.add(result("greedy", "Greedy insertion", false, new GreedyInsertionSolver(), scenario.graph(), start, period, options));
        results.add(result("exact", "Branch and bound", false, new BranchAndBoundSolver(), scenario.graph(), start, period, options));
        return Map.of("scenario", scenario(scenario), "startTime", start, "durationMinutes", period,
                "deadline", start + period, "timeLimitMs", options.timeLimitMillis(),
                "maxDestinations", options.maxDestinations(), "results", results);
    }
    private static Map<String, Object> result(String id, String name, boolean baseline, RouteSolver solver,
                                              DestinationGraph graph, double start, double period, SolverOptions options) {
        RouteResult result = solver.solve(graph, start, period, options);
        var schedule = result.schedule();
        if (schedule == null || !ScheduleEvaluator.evaluate(graph, schedule.route(), start, period).feasible())
            throw new IllegalStateException("Solver returned an invalid schedule");
        List<Object> visits = new ArrayList<>();
        for (int i = 0; i < schedule.visits().size(); i++) {
            var visit = schedule.visits().get(i);
            int prev = i == 0 ? 0 : schedule.visits().get(i - 1).vertex();
            visits.add(Map.of("vertex", visit.vertex(), "arrival", visit.arrival(), "visitTime", visit.visitTime(),
                    "waiting", visit.waiting(), "legDistanceKm", graph.distance(prev, visit.vertex()),
                    "legTravelMinutes", graph.travelMinutes(prev, visit.vertex())));
        }
        Set<Integer> selected = new HashSet<>(schedule.route());
        List<Integer> skipped = new ArrayList<>();
        for (int i = 1; i < graph.size(); i++) if (!selected.contains(i)) skipped.add(i);
        Map<String, Object> response = new LinkedHashMap<>();
        response.put("id", id); response.put("name", name); response.put("baseline", baseline);
        response.put("status", result.status().name()); response.put("message", result.message());
        response.put("visitedCount", result.visitedCount()); response.put("elapsedMs", result.elapsedMillis());
        response.put("workCount", result.exploredStates()); response.put("route", schedule.route());
        response.put("distanceKm", schedule.distanceKm()); response.put("travelMinutes", schedule.travelMinutes());
        response.put("waitingMinutes", schedule.waitingMinutes()); response.put("finishTime", schedule.finishTime());
        response.put("visits", visits); response.put("skipped", skipped);
        return response;
    }
}
