package evaluation.app;

import algorithms.*;
import app.GenerationOptions;
import app.ScenarioFiles;
import evaluation.algorithms.NearestNeighbourSolver;
import graph.GeoNamesLoader;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/**
 * Averaged benchmark: N seeded random scenarios per configuration, each solved by nearest, greedy and exact.
 * Usage: ./evaluation/benchmark.sh [--scenarios N] [--seed S] [--out file] [--source MY.txt] [--time-limit-ms ms]
 *
 * Output JSON schema (evaluation/web/benchmark-data.json):
 * {
 *   "generator": "BenchmarkMain", "baseSeed": long, "scenariosPerConfig": int, "exactTimeLimitMs": long,
 *   "source": "submission/inputs/MY.txt", "algorithms": ["nearest","greedy","exact"],
 *   "totals": { "scenarios": int, "exactLimitHit": int },
 *   "configs": [ {
 *     "customers": int (5/8/10/12), "windowMode": "slack"|"blocks", "periodMinutes": number,
 *     "scenarios": int, "exactLimitHit": int (excluded from quality stats), "included": int,
 *     "algorithms": { "nearest"|"greedy"|"exact": {
 *         "visits": {"mean","median","stdDev"}   // over included scenarios
 *         "optimalShare": 0..1                   // same visits as exact and distance <= exact (+1e-9)
 *         "visitsPctOfExact": mean of visits/exactVisits*100 (scenarios where exact visits > 0)
 *         "distanceRatio": mean of distance/exactDistance (same visits as exact and exact distance > 0)
 *         "runtimeMs": {"mean","max"}            // timing; not deterministic, all other fields are
 *     } }
 *   } ]
 * }
 * Each scenario uses a seeded random start clock (06:00/08:00/12:00/18:00) and a seeded random customer
 * selection (feature class P, admin1 14, depot 1735161). Same base seed gives identical output apart from runtimeMs.
 */
public final class BenchmarkMain {
    static final String[] IDS = {"nearest", "greedy", "exact"};
    static final String[] CLOCKS = {"06:00", "08:00", "12:00", "18:00"};
    static final int[] COUNTS = {5, 8, 10, 12};
    static final double[] PERIODS = {120, 240};
    static final String[] MODES = {GenerationOptions.SLACK, GenerationOptions.BLOCKS};

    public static void main(String[] args) {
        try { run(args); }
        catch (Exception error) { System.err.println("Error: " + error.getMessage()); System.exit(1); }
    }
    private static void run(String[] args) throws Exception {
        int n = 100; long seed = 42, limit = 3000; Path out = Path.of("../evaluation/web/benchmark-data.json");
        Path source = Path.of("inputs/MY.txt");
        if (args.length == 1 && args[0].equals("--help")) {
            System.out.println("Benchmark: ./evaluation/benchmark.sh [--scenarios N] [--seed S] [--out file] [--source file] [--time-limit-ms ms]");
            return;
        }
        for (int i = 0; i < args.length; i += 2) {
            if (i + 1 == args.length) throw new IllegalArgumentException("Missing value for " + args[i]);
            switch (args[i]) {
                case "--scenarios" -> n = Integer.parseInt(args[i + 1]);
                case "--seed" -> seed = Long.parseLong(args[i + 1]);
                case "--out" -> out = Path.of(args[i + 1]);
                case "--source" -> source = Path.of(args[i + 1]);
                case "--time-limit-ms" -> limit = Long.parseLong(args[i + 1]);
                default -> throw new IllegalArgumentException("Unknown option " + args[i]);
            }
        }
        if (n < 1) throw new IllegalArgumentException("--scenarios must be at least 1");
        Map<String, Object> data = benchmark(source, n, seed, limit, COUNTS, PERIODS);
        if (out.getParent() != null) Files.createDirectories(out.getParent());
        Files.writeString(out, Json.stringify(data) + "\n");
        System.out.println("Wrote " + out + " (" + ((List<?>) data.get("configs")).size() + " configurations)");
    }

    private record Run(int visits, double distance, double ms, boolean limit) {}

    public static Map<String, Object> benchmark(Path source, int scenarios, long seed, long limitMs,
                                                int[] counts, double[] periods) throws IOException {
        List<Object> configs = new ArrayList<>();
        int total = 0, hits = 0, configIndex = 0;
        Path tmp = Files.createTempDirectory("benchmark-");
        try {
            for (int customers : counts) for (String mode : MODES) for (double period : periods) {
                configIndex++;
                List<Run[]> rows = new ArrayList<>();
                for (int s = 0; s < scenarios; s++) {
                    long scenarioSeed = seed * 1_000_003L + configIndex * 1009L + s;
                    String clock = CLOCKS[new Random(scenarioSeed).nextInt(CLOCKS.length)];
                    var selection = new GeoNamesLoader.Selection(customers + 1, "P", "14", 1735161L, "random", scenarioSeed);
                    ScenarioFiles.generate(source, tmp, new GenerationOptions(selection, 40, clock, period, 30, mode));
                    var scenario = ScenarioFiles.load(tmp, null);
                    SolverOptions solver = new SolverOptions(Math.max(15, customers + 1), limitMs);
                    RouteSolver[] solvers = {new NearestNeighbourSolver(), new GreedyInsertionSolver(), new BranchAndBoundSolver()};
                    Run[] row = new Run[3];
                    for (int a = 0; a < 3; a++) {
                        long t0 = System.nanoTime();
                        RouteResult r = solvers[a].solve(scenario.graph(), 0, period, solver);
                        double ms = (System.nanoTime() - t0) / 1e6;
                        double dist = r.schedule() == null ? 0 : r.schedule().distanceKm();
                        row[a] = new Run(r.visitedCount(), dist, ms, r.status() == RouteResult.Status.SEARCH_LIMIT_REACHED);
                    }
                    rows.add(row);
                }
                int limited = (int) rows.stream().filter(r -> r[2].limit()).count();
                total += scenarios; hits += limited;
                Map<String, Object> config = new LinkedHashMap<>();
                config.put("customers", customers); config.put("windowMode", mode); config.put("periodMinutes", period);
                config.put("scenarios", scenarios); config.put("exactLimitHit", limited);
                List<Run[]> included = rows.stream().filter(r -> !r[2].limit()).toList();
                config.put("included", included.size());
                Map<String, Object> algorithms = new LinkedHashMap<>();
                for (int a = 0; a < 3; a++) algorithms.put(IDS[a], stats(included, a));
                config.put("algorithms", algorithms);
                configs.add(config);
            }
        } finally {
            try (var files = Files.list(tmp)) { for (Path p : files.toList()) Files.deleteIfExists(p); }
            Files.deleteIfExists(tmp);
        }
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("generator", "BenchmarkMain"); root.put("baseSeed", seed); root.put("scenariosPerConfig", scenarios);
        root.put("exactTimeLimitMs", limitMs); root.put("source", "submission/inputs/MY.txt");
        root.put("algorithms", List.of(IDS));
        root.put("totals", ordered("scenarios", total, "exactLimitHit", hits));
        root.put("configs", configs);
        return root;
    }

    /** Insertion-ordered pairs so the JSON text is stable (Map.of order varies per JVM run). */
    private static Map<String, Object> ordered(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    private static Map<String, Object> stats(List<Run[]> rows, int a) {
        double[] v = rows.stream().mapToDouble(r -> r[a].visits()).toArray();
        double mean = Arrays.stream(v).average().orElse(0);
        double[] sorted = v.clone(); Arrays.sort(sorted);
        double median = sorted.length == 0 ? 0 : sorted.length % 2 == 1 ? sorted[sorted.length / 2]
                : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
        double var = Arrays.stream(v).map(x -> (x - mean) * (x - mean)).average().orElse(0);
        int optimal = 0, pctN = 0, ratioN = 0; double pct = 0, ratio = 0;
        for (Run[] r : rows) {
            Run x = r[a], e = r[2];
            if (x.visits() == e.visits() && x.distance() <= e.distance() + 1e-9) optimal++;
            if (e.visits() > 0) { pct += 100.0 * x.visits() / e.visits(); pctN++; }
            if (x.visits() == e.visits() && e.distance() > 0) { ratio += x.distance() / e.distance(); ratioN++; }
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("visits", ordered("mean", mean, "median", median, "stdDev", Math.sqrt(var)));
        m.put("optimalShare", rows.isEmpty() ? 0.0 : (double) optimal / rows.size());
        m.put("visitsPctOfExact", pctN == 0 ? 100.0 : pct / pctN);
        m.put("distanceRatio", ratioN == 0 ? 1.0 : ratio / ratioN);
        m.put("runtimeMs", ordered("mean", rows.stream().mapToDouble(r -> r[a].ms()).average().orElse(0),
                "max", rows.stream().mapToDouble(r -> r[a].ms()).max().orElse(0)));
        return m;
    }
}
