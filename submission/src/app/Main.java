package app;

import algorithms.*;
import graph.*;
import java.nio.file.*;
import java.util.*;

public final class Main {
    public static void main(String[] args) {
        try { run(args); }
        catch (Exception e) { System.err.println("Error: " + e.getMessage()); System.exit(1); }
    }
    private static void run(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--help")) { usage(); return; }
        if (args.length > 0 && args[0].equals("--generate")) {
            generate(args);
            return;
        }
        Path data = Path.of("data");
        Double speed = null;
        String requestedStart = null;
        Double requestedDuration = null;
        String algorithm = "both";
        int cap = 15; long milliseconds = 10_000;
        for (int i = 0; i < args.length; i += 2) {
            if (i + 1 >= args.length) throw new IllegalArgumentException("Missing value for " + args[i]);
            switch (args[i]) {
                case "--data" -> data = Path.of(args[i + 1]);
                case "--speed" -> speed = Double.parseDouble(args[i + 1]);
                case "--start-time" -> requestedStart = args[i + 1];
                case "--duration-minutes" -> requestedDuration = Double.parseDouble(args[i + 1]);
                case "--algorithm" -> algorithm = args[i + 1];
                case "--max-destinations" -> cap = Integer.parseInt(args[i + 1]);
                case "--time-limit-ms" -> milliseconds = Long.parseLong(args[i + 1]);
                default -> throw new IllegalArgumentException("Unknown option " + args[i]);
            }
        }
        if (!Set.of("all", "both", "greedy", "exact").contains(algorithm))
            throw new IllegalArgumentException("Algorithm must be both, greedy or exact (all is an alias for both)");
        var scenario = ScenarioFiles.load(data, speed);
        double start = parseStart(requestedStart, scenario.clockStartMinutes());
        double duration = requestedDuration == null ? scenario.durationMinutes() : requestedDuration;
        double deadline = ScheduleEvaluator.deadline(scenario.graph(), start, duration);
        var options = new SolverOptions(cap, milliseconds);
        System.out.printf(Locale.ROOT, "SIMULATION: %d vertices including depot; %.2f km/h; zero service time.%n",
                scenario.graph().size(), scenario.speedKmh());
        System.out.println("Haversine distances and simulated windows; travel is not based on roads.");
        System.out.println("Objective: maximize customer visits, then minimize distance. Depot does not count.");
        System.out.printf(Locale.ROOT, "Departure: %s; period: %.3f min; return by: %s%n",
                clock(start, scenario.clockStartMinutes()), duration, clock(deadline, scenario.clockStartMinutes()));
        System.out.println("Times below are minutes from " + clock(0, scenario.clockStartMinutes()) + ". Waiting and return travel count.");
        if (Set.of("all", "both", "greedy").contains(algorithm)) print("Greedy insertion", new GreedyInsertionSolver().solve(scenario.graph(), start, duration, options), scenario, duration);
        if (Set.of("all", "both", "exact").contains(algorithm)) print("Branch and bound", new BranchAndBoundSolver().solve(scenario.graph(), start, duration, options), scenario, duration);
    }
    private static void generate(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("Use --generate <MY.txt> [selection options]");
        int count = 10; String featureClass = "P", admin1 = "14", method = "population", startClock = "08:00";
        long depot = 1735161L, seed = 42; double speed = 40, duration = 120, slack = 30;
        for (int i = 2; i < args.length; i += 2) {
            if (i + 1 >= args.length) throw new IllegalArgumentException("Missing generation value for " + args[i]);
            switch (args[i]) {
                case "--count" -> count = Integer.parseInt(args[i + 1]);
                case "--feature-class" -> featureClass = args[i + 1];
                case "--admin1" -> admin1 = args[i + 1];
                case "--depot" -> depot = Long.parseLong(args[i + 1]);
                case "--selection" -> method = args[i + 1];
                case "--seed" -> seed = Long.parseLong(args[i + 1]);
                case "--speed" -> speed = Double.parseDouble(args[i + 1]);
                case "--start-clock" -> startClock = args[i + 1];
                case "--duration-minutes" -> duration = Double.parseDouble(args[i + 1]);
                case "--window-slack-minutes" -> slack = Double.parseDouble(args[i + 1]);
                default -> throw new IllegalArgumentException("Unknown generation option " + args[i]);
            }
        }
        var selection = new GeoNamesLoader.Selection(count, featureClass, admin1, depot, method, seed);
        var options = new GenerationOptions(selection, speed, startClock, duration, slack);
        ScenarioFiles.generate(Path.of(args[1]), Path.of("data"), options);
        System.out.printf("Replaced data/: %d destinations including depot (%d potential visits); %s selection, seed %d.%n",
                count, count - 1, method, seed);
    }

    private static void print(String name, RouteResult result, ScenarioFiles.Scenario scenario, double duration) {
        DestinationGraph graph = scenario.graph();
        System.out.printf(Locale.ROOT, "%n%s: %s%n%s%nRuntime: %.3f ms; explored candidates/states: %d%n",
                name, result.status(), result.message(), result.elapsedMillis(), result.exploredStates());
        if (!result.hasRoute()) { System.out.println("No feasible route returned."); return; }
        var schedule = result.schedule();
        // Recheck the complete result at the application boundary.
        var check = ScheduleEvaluator.evaluate(graph, schedule.route(), schedule.visits().get(0).arrival(), duration);
        if (!check.feasible()) throw new IllegalStateException("Solver returned invalid route: " + check.reason());
        Set<Integer> visited = new HashSet<>(schedule.route());
        List<String> skipped = new ArrayList<>();
        for (int v = 1; v < graph.size(); v++) if (!visited.contains(v))
            skipped.add(graph.destination(v).geoNameId() + " " + graph.destination(v).name());
        System.out.printf("Visited: %d/%d customers%n", result.visitedCount(), graph.size() - 1);
        System.out.println("Skipped: " + (skipped.isEmpty() ? "none" : String.join(", ", skipped)));
        System.out.printf("%-10s %-22s %10s %10s %10s %-10s %-22s%n",
                "GeoNameID", "Destination", "Arrival", "Visit", "Wait", "Clock", "Window (minutes)");
        for (int i = 0; i < schedule.visits().size(); i++) {
            var visit = schedule.visits().get(i); var d = graph.destination(visit.vertex());
            String window = visit.vertex() == 0 ? (i == 0 ? "depot departure" : "within trip budget")
                    : String.format(Locale.ROOT, "[%.3f, %.3f]", d.opensAt(), d.closesAt());
            System.out.printf(Locale.ROOT, "%-10d %-22s %10.3f %10.3f %10.3f %-10s %-22s%n",
                    d.geoNameId(), d.name(), visit.arrival(), visit.visitTime(), visit.waiting(),
                    clock(visit.visitTime(), scenario.clockStartMinutes()), window);
        }
        System.out.printf(Locale.ROOT, "Distance: %.6f km; travel: %.6f min; waiting: %.6f min; finish: %.6f min (%s)%n",
                schedule.distanceKm(), schedule.travelMinutes(), schedule.waitingMinutes(), schedule.finishTime(),
                clock(schedule.finishTime(), scenario.clockStartMinutes()));
    }
    private static double parseStart(String requested, int origin) {
        if (requested == null) return 0;
        if (!requested.contains(":")) return Double.parseDouble(requested);
        String[] parts = requested.split(":", -1);
        if (parts.length != 2) throw new IllegalArgumentException("Start clock must be HH:mm");
        int hours = Integer.parseInt(parts[0]), minutes = Integer.parseInt(parts[1]);
        if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59)
            throw new IllegalArgumentException("Invalid start clock");
        int offset = hours * 60 + minutes - origin;
        if (offset < 0) throw new IllegalArgumentException("Start clock precedes the window origin; use a later clock or a next-day minute offset");
        return offset;
    }
    private static String clock(double elapsed, int startClock) {
        long seconds = Math.round((elapsed + startClock) * 60);
        long day = seconds / 86400; seconds %= 86400;
        return String.format(Locale.ROOT, "%02d:%02d:%02d%s", seconds / 3600, (seconds / 60) % 60,
                seconds % 60, day == 0 ? "" : "+" + day + "d");
    }
    private static void usage() {
        System.out.println("""
                Run from the project directory: java -cp out app.Main [options]
                  --data <directory>       Scenario directory (default data)
                  --algorithm both|greedy|exact (all is an alias for both)
                  --speed <km/h>           Override simulated speed (default 40)
                  --start-time <HH:mm>     Departure clock (default scenario startClock)
                  --duration-minutes <n>   Trip period INCLUDING return (default config, 120)
                  --start-time <minutes>   Alternatively, offset from scenario startClock
                  --max-destinations <n>   Exact solver cap including depot (default 15)
                  --time-limit-ms <ms>     Each solver budget; 0 returns current subset (default 10000)
                Generate and REPLACE the current data/ scenario (MY.txt is left unchanged):
                  java -cp out app.Main --generate <MY.txt> [options]
                  --count <n>              Total vertices INCLUDING depot (default 10)
                  --feature-class <class>  Customer feature class or all (default P)
                  --admin1 <code>          Customer region code or all (default 14)
                  --depot <id>             Depot GeoNameID (default 1735161)
                  --selection population|random  Customer selection (default population)
                  --seed <integer>         Reproducible selection/window seed (default 42)
                  --speed <km/h> --start-clock <HH:mm> --duration-minutes <minutes>
                  --window-slack-minutes <minutes>  Slack around generated visits (default 30)
                """);
    }
}
