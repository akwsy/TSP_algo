package tests;

import evaluation.app.BenchmarkMain;
import evaluation.app.Json;
import java.nio.file.Path;
import java.util.*;

/** Tiny-run checks for the averaged benchmark: determinism, schema and exact-never-worse. */
public final class BenchmarkTest {
    private static int assertions;
    private static void check(boolean ok, String message) { assertions++; if (!ok) throw new AssertionError(message); }
    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object o) { return (Map<String, Object>) o; }
    /** JSON text with the non-deterministic timing blocks removed. */
    private static String stable(Map<String, Object> data) {
        return Json.stringify(data).replaceAll("\"runtimeMs\":\\{[^}]*\\}", "\"runtimeMs\":0");
    }
    public static void main(String[] args) throws Exception {
        Path source = Path.of("inputs/MY.txt");
        int[] counts = {5, 8}; double[] periods = {120};
        var a = BenchmarkMain.benchmark(source, 3, 7, 3000, counts, periods);
        var b = BenchmarkMain.benchmark(source, 3, 7, 3000, counts, periods);
        check(stable(a).equals(stable(b)), "Same seed gives identical output apart from runtimes");
        check(!stable(a).equals(stable(BenchmarkMain.benchmark(source, 3, 8, 3000, counts, periods))), "Different seed changes scenarios");
        for (String key : List.of("generator", "baseSeed", "scenariosPerConfig", "exactTimeLimitMs", "algorithms", "totals", "configs"))
            check(a.containsKey(key), "Top-level key " + key);
        List<Object> configs = (List<Object>) a.get("configs");
        check(configs.size() == 4, "2 counts x 2 modes x 1 period");
        for (Object c : configs) {
            var config = map(c);
            for (String key : List.of("customers", "windowMode", "periodMinutes", "scenarios", "exactLimitHit", "included", "algorithms"))
                check(config.containsKey(key), "Config key " + key);
            check((int) config.get("exactLimitHit") + (int) config.get("included") == (int) config.get("scenarios"), "Limit hits are counted and excluded");
            var algorithms = map(config.get("algorithms"));
            check(algorithms.keySet().equals(Set.of("nearest", "greedy", "exact")), "Three algorithms");
            double exactVisits = ((Number) map(map(algorithms.get("exact")).get("visits")).get("mean")).doubleValue();
            for (var entry : algorithms.entrySet()) {
                var stats = map(entry.getValue());
                for (String key : List.of("visits", "optimalShare", "visitsPctOfExact", "distanceRatio", "runtimeMs"))
                    check(stats.containsKey(key), "Stats key " + key);
                for (String key : List.of("mean", "median", "stdDev")) check(map(stats.get("visits")).containsKey(key), "visits." + key);
                for (String key : List.of("mean", "max")) check(map(stats.get("runtimeMs")).containsKey(key), "runtimeMs." + key);
                double visits = ((Number) map(stats.get("visits")).get("mean")).doubleValue();
                check(visits <= exactVisits + 1e-9, "Exact never visits fewer than " + entry.getKey());
                check(((Number) stats.get("visitsPctOfExact")).doubleValue() <= 100 + 1e-9, "Visits never exceed exact");
                double share = ((Number) stats.get("optimalShare")).doubleValue();
                check(share >= 0 && share <= 1, "Share in range");
            }
            check(((Number) map(algorithms.get("exact")).get("optimalShare")).doubleValue() == 1.0 || (int) config.get("included") == 0, "Exact is optimal against itself");
        }
        System.out.println("PASS: BenchmarkTest " + assertions + " assertions");
    }
}
