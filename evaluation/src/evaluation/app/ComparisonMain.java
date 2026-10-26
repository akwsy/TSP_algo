package evaluation.app;

import algorithms.*;
import app.ScenarioFiles;
import evaluation.algorithms.NearestNeighbourSolver;
import java.nio.file.*;
import java.util.*;

/** Evaluation-only CLI. Submission Main deliberately does not include the baseline. */
public final class ComparisonMain {
    public static void main(String[] args) {
        try { run(args); }
        catch (Exception error) { System.err.println("Error: " + error.getMessage()); System.exit(1); }
    }
    private static void run(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--help")) {
            System.out.println("""
                    Evaluation comparison: ./evaluation/compare.sh [options]
                      --algorithm all|nearest|greedy|exact (both is an alias for all)
                      --data <directory relative to submission/>
                      --start-time <HH:mm or minute offset>
                      --duration-minutes <period including waiting and return>
                      --speed <km/h> --time-limit-ms <ms> --max-destinations <n>
                    """); return;
        }
        Path data = Path.of("data"); Double speed = null, period = null;
        String startInput = null, choice = "all"; int cap = 15; long milliseconds = 10000;
        for (int i = 0; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing value for " + args[i]);
            switch (args[i]) {
                case "--data" -> data = Path.of(args[i + 1]);
                case "--start-time" -> startInput = args[i + 1];
                case "--duration-minutes" -> period = Double.parseDouble(args[i + 1]);
                case "--speed" -> speed = Double.parseDouble(args[i + 1]);
                case "--time-limit-ms" -> milliseconds = Long.parseLong(args[i + 1]);
                case "--max-destinations" -> cap = Integer.parseInt(args[i + 1]);
                case "--algorithm" -> choice = args[i + 1];
                default -> throw new IllegalArgumentException("Unknown option " + args[i]);
            }
        }
        if (!Set.of("all", "both", "nearest", "greedy", "exact").contains(choice))
            throw new IllegalArgumentException("Unknown algorithm");
        var scenario = ScenarioFiles.load(data, speed);
        double start = start(startInput, scenario.clockStartMinutes());
        double duration = period == null ? scenario.durationMinutes() : period;
        ScheduleEvaluator.deadline(scenario.graph(), start, duration);
        var options = new SolverOptions(cap, milliseconds);
        System.out.printf(Locale.ROOT, "Evaluation: %d potential visits, departure %s, period %.3f min, return by %s.%n",
                scenario.graph().size() - 1, clock(start, scenario.clockStartMinutes()), duration,
                clock(start + duration, scenario.clockStartMinutes()));
        System.out.println("Simulated travel/windows; maximize visits, then minimize distance. Depot excluded.");
        var solvers = new LinkedHashMap<String, RouteSolver>();
        solvers.put("nearest", new NearestNeighbourSolver()); solvers.put("greedy", new GreedyInsertionSolver());
        solvers.put("exact", new BranchAndBoundSolver());
        for (var entry : solvers.entrySet()) {
            if (!Set.of("all", "both", entry.getKey()).contains(choice)) continue;
            String name = switch (entry.getKey()) { case "nearest" -> "Nearest neighbour (baseline)"; case "greedy" -> "Greedy insertion"; default -> "Branch and bound"; };
            var result = entry.getValue().solve(scenario.graph(), start, duration, options);
            var s = result.schedule();
            if (s == null || !ScheduleEvaluator.evaluate(scenario.graph(), s.route(), start, duration).feasible())
                throw new IllegalStateException("Invalid route returned");
            System.out.printf(Locale.ROOT, "%n%s: %s%n%s%nVisited: %d/%d customers%nDistance: %.6f km; travel: %.6f min; waiting: %.6f min; return: %s%nRuntime: %.3f ms; candidates/states: %d%n",
                    name, result.status(), result.message(), result.visitedCount(), scenario.graph().size() - 1,
                    s.distanceKm(), s.travelMinutes(), s.waitingMinutes(), clock(s.finishTime(), scenario.clockStartMinutes()), result.elapsedMillis(), result.exploredStates());
            System.out.println("Route: " + String.join(" -> ", s.route().stream().map(i -> scenario.graph().destination(i).name()).toList()));
            Set<Integer> visited = new HashSet<>(s.route()); List<String> skipped = new ArrayList<>();
            for (int i = 1; i < scenario.graph().size(); i++) if (!visited.contains(i)) skipped.add(scenario.graph().destination(i).name());
            System.out.println("Skipped: " + (skipped.isEmpty() ? "none" : String.join(", ", skipped)));
            for (var visit : s.visits()) {
                var d = scenario.graph().destination(visit.vertex());
                System.out.printf(Locale.ROOT, "  %d %s: arrival %s; visit %s; wait %.3f min%n", d.geoNameId(), d.name(),
                        clock(visit.arrival(), scenario.clockStartMinutes()), clock(visit.visitTime(), scenario.clockStartMinutes()), visit.waiting());
            }
        }
    }
    private static double start(String text, int origin) {
        if (text == null) return 0;
        if (!text.contains(":")) return Double.parseDouble(text);
        if (!text.matches("(?:[01][0-9]|2[0-3]):[0-5][0-9]")) throw new IllegalArgumentException("Clock must be HH:mm");
        String[] parts = text.split(":");
        int offset = Integer.parseInt(parts[0]) * 60 + Integer.parseInt(parts[1]) - origin;
        if (offset < 0) throw new IllegalArgumentException("Start clock precedes the window origin");
        return offset;
    }
    private static String clock(double minutes, int origin) {
        long seconds = Math.round((minutes + origin) * 60), day = seconds / 86400;
        return String.format(Locale.ROOT, "%02d:%02d:%02d%s", (seconds / 3600) % 24, (seconds / 60) % 60,
                seconds % 60, day == 0 ? "" : "+" + day + "d");
    }
}
