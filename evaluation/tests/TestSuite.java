package tests;

import algorithms.*;
import evaluation.algorithms.NearestNeighbourSolver;
import app.ScenarioFiles;
import app.GenerationOptions;
import graph.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import static algorithms.RouteResult.Status.*;

/** Independent subset/permutation oracle; no external test dependencies. */
public final class TestSuite {
    private static int assertions;
    private static final SolverOptions OPTIONS = SolverOptions.defaults();
    private record Score(int count, double distance) {}
    public static void main(String[] args) throws Exception {
        inputValidation(); boundaries(); baselineCases(); objectivesAndLimits(); oracleCases(); scenariosAndCli();
        System.out.println("PASS: " + assertions + " assertions; 100 independent subset-oracle cases plus focused fixtures.");
    }
    private static Destination d(long id, double lat, double lon, double open, double close) {
        return new Destination(id, "Place " + id, lat, lon, open, close);
    }
    private static Destination depot() { return d(1, 0, 0, 0, Double.MAX_VALUE); }
    private static void check(boolean condition, String message) {
        assertions++; if (!condition) throw new AssertionError(message);
    }
    private static void near(double a, double b, String message) {
        check(Math.abs(a - b) < 1e-7, message + ": " + a + " vs " + b);
    }
    @FunctionalInterface private interface Operation { void run() throws Exception; }
    private static void rejects(Operation operation) throws Exception {
        try { operation.run(); } catch (IllegalArgumentException | IOException e) { assertions++; return; }
        throw new AssertionError("Expected rejection");
    }
    private static void inputValidation() throws Exception {
        var g = new DestinationGraph(List.of(depot(), d(2, 0, 1, 0, 1000)), 60);
        near(g.distance(0, 1), 111.1950802335329, "Equatorial distance");
        near(g.distance(0, 1), g.distance(1, 0), "Symmetric graph");
        near(g.travelMinutes(0, 1), g.distance(0, 1), "Speed conversion");
        check(g.indexOf(2) == 1, "ID lookup");
        rejects(() -> g.indexOf(3));
        rejects(() -> new DestinationGraph(List.of(depot(), depot()), 40));
        rejects(() -> d(2, 91, 0, 0, 1));
        rejects(() -> d(2, 0, Double.NaN, 0, 1));
        rejects(() -> d(2, 0, 0, Double.NaN, 1));
        rejects(() -> d(2, 0, 0, 2, 1));
        rejects(() -> new DestinationGraph(List.of(depot()), 0));
        rejects(() -> new DestinationGraph(List.of(depot()), Double.POSITIVE_INFINITY));
        rejects(() -> new SolverOptions(0, 1)); rejects(() -> new SolverOptions(1, -1));
        for (RouteSolver solver : List.of(new NearestNeighbourSolver(), new GreedyInsertionSolver(), new BranchAndBoundSolver())) {
            rejects(() -> solver.solve(g, 0, -1, OPTIONS));
            rejects(() -> solver.solve(g, 0, Double.NaN, OPTIONS));
            rejects(() -> solver.solve(g, 0, Double.POSITIVE_INFINITY, OPTIONS));
            rejects(() -> solver.solve(g, Double.NaN, 10, OPTIONS));
            rejects(() -> solver.solve(g, -1, 10, OPTIONS));
            rejects(() -> solver.solve(g, Double.MAX_VALUE, Double.MAX_VALUE, OPTIONS));
        }
    }
    private static void boundaries() {
        var g = new DestinationGraph(List.of(depot(), d(2, 0, .01, 10, 10)), 60);
        double back = g.travelMinutes(1, 0);
        var e = ScheduleEvaluator.evaluate(g, List.of(0, 1, 0), 0, 10 + back);
        check(e.feasible(), "Early arrival, exact window close and exact period endpoint");
        near(e.schedule().visits().get(1).visitTime(), 10, "Wait until window opens");
        near(e.schedule().waitingMinutes(), 10 - back, "Waiting counted");
        near(e.schedule().finishTime(), 10 + back, "Zero service and return");
        check(!ScheduleEvaluator.evaluate(g, List.of(0, 1, 0), 0, 10 + back - .001).feasible(), "Return after deadline forbidden");
        check(!ScheduleEvaluator.evaluate(g, List.of(0, 1, 0), 10, 1).feasible(), "Late customer forbidden");
        check(ScheduleEvaluator.evaluate(g, List.of(0, 0), 0, 0).feasible(), "Skipping all is feasible");
        check(!ScheduleEvaluator.evaluate(g, List.of(0, 1, 1, 0), 0, 100).feasible(), "No repeated visits");
        check(!ScheduleEvaluator.evaluate(g, List.of(0, 1), 0, 100).feasible(), "Return required");
        check(!ScheduleEvaluator.evaluate(g, List.of(0, 9, 0), 0, 100).feasible(), "Unknown index");
        var boundary = new DestinationGraph(List.of(depot(), d(2, 0, .01, 0, back)), 60);
        check(ScheduleEvaluator.evaluate(boundary, List.of(0, 1, 0), 0, 2 * back).feasible(), "Arrival exactly at close");
        var shortDepot = new DestinationGraph(List.of(d(1, 0, 0, 0, 1), d(2, 0, .01, 10, 20)), 60);
        check(ScheduleEvaluator.evaluate(shortDepot, List.of(0, 1, 0), 0, 20).feasible(), "Depot window is departure-only; period bounds return");
        for (RouteSolver solver : List.of(new NearestNeighbourSolver(), new GreedyInsertionSolver(), new BranchAndBoundSolver())) {
            check(solver.solve(g, 0, 5, OPTIONS).visitedCount() == 0, "Waiting consumes budget");
            check(solver.solve(g, 0, 10 + back, OPTIONS).visitedCount() == 1, "Visit fits inclusive deadline");
        }
    }
    private static void baselineCases() {
        var nearest = new NearestNeighbourSolver();
        // The nearest location is feasible but causes a long wait, losing an early visit.
        var g = new DestinationGraph(List.of(depot(), d(2, 0, .001, 10, 20), d(3, 0, .01, 0, 5)), 60);
        var baseline = nearest.solve(g, 0, 30, OPTIONS);
        check(baseline.schedule().route().equals(List.of(0, 1, 0)), "Nearest by distance, not earliest opening");
        check(new BranchAndBoundSolver().solve(g, 0, 30, OPTIONS).visitedCount() == 2, "Baseline can lose achievable visits");
        validate(g, baseline, 0, 30);
        var lateNearest = new DestinationGraph(List.of(depot(), d(2, 0, .001, 0, .001), d(3, 0, .01, 0, 10)), 60);
        check(nearest.solve(lateNearest, 0, 10, OPTIONS).schedule().route().equals(List.of(0, 2, 0)), "Skip infeasible nearest location");
        var tooFar = new DestinationGraph(List.of(depot(), d(2, 0, .01, 0, 10)), 60);
        check(nearest.solve(tooFar, 0, tooFar.travelMinutes(0, 1) + .1, OPTIONS).visitedCount() == 0, "Baseline reserves return time");
        var tied = new DestinationGraph(List.of(depot(), d(30, 0, .01, 0, 100), d(20, 0, -.01, 0, 100)), 60);
        check(nearest.solve(tied, 0, 100, OPTIONS).schedule().route().get(1) == 2, "Equal distance breaks by GeoNameID");
        validate(tied, nearest.solve(tied, 0, 100, OPTIONS), 0, 100);
    }
    private static void objectivesAndLimits() {
        var exact = new BranchAndBoundSolver();
        var g = new DestinationGraph(List.of(depot(), d(2, 0, .01, 0, 100), d(3, 0, .02, 0, 100)), 60);
        var best = exact.solve(g, 0, 10, OPTIONS);
        check(best.status() == OPTIMAL && best.visitedCount() == 2, "Visit count takes priority over distance");
        check(best.schedule().distanceKm() > 2 * g.distance(0, 1), "More visits can mean greater distance");
        validate(g, best, 0, 10);
        var opposite = new DestinationGraph(List.of(depot(), d(2, 0, .01, 0, 100), d(3, 0, -.02, 0, 100)), 60);
        var tie = exact.solve(opposite, 0, 5, OPTIONS);
        check(tie.visitedCount() == 1 && tie.schedule().route().contains(1), "Equal count: shortest distance wins");
        var impossible = new DestinationGraph(List.of(depot(), d(2, 0, 1, 0, 1)), 40);
        var empty = exact.solve(impossible, 0, 10, OPTIONS);
        check(empty.status() == OPTIMAL && empty.visitedCount() == 0, "Unreachable customer is skipped, not infeasibility");
        for (RouteSolver solver : List.of(new NearestNeighbourSolver(), new GreedyInsertionSolver(), exact)) {
            var limit = solver.solve(g, 0, 10, new SolverOptions(15, 0));
            check(limit.status() == SEARCH_LIMIT_REACHED && limit.hasRoute(), "Timeout retains feasible route");
            validate(g, limit, 0, 10);
            var zero = solver.solve(g, 0, 0, OPTIONS);
            check(zero.visitedCount() == 0, "Zero-period noncoincident customers");
        }
        var cap = exact.solve(g, 0, 10, new SolverOptions(1, 10000));
        check(cap.status() == SEARCH_LIMIT_REACHED && cap.visitedCount() == 0 && cap.hasRoute(), "Cap gives no optimality proof");
        var alone = new DestinationGraph(List.of(depot()), 40);
        validate(alone, exact.solve(alone, 0, 0, OPTIONS), 0, 0);
        var coincident = new DestinationGraph(List.of(depot(), d(2, 0, 0, 0, 0)), 40);
        check(exact.solve(coincident, 0, 0, OPTIONS).visitedCount() == 1, "Zero-travel visit fits zero period");
        var trap = new DestinationGraph(List.of(depot(),
                d(2, -.02382496093631371, -.022477728757586544, 1.4443513989645491, 6.467078218891089),
                d(3, -.03536008198012981, .02956491997173371, 9.027127360913646, 17.761767277751815),
                d(4, -.004305525994991732, .030630243259892463, 9.168232931644853, 12.909639708186457),
                d(5, -.007029334037919208, .020143180728838674, 4.790789109424437, 11.05868102470942)), 60);
        var greedy = new GreedyInsertionSolver().solve(trap, 0, 100, OPTIONS);
        var optimal = exact.solve(trap, 0, 100, OPTIONS);
        check(greedy.visitedCount() < optimal.visitedCount() && optimal.visitedCount() == 4, "Greedy subset can be suboptimal");
        validate(trap, greedy, 0, 100); validate(trap, optimal, 0, 100);
    }
    private static void oracleCases() {
        Random random = new Random(91042);
        for (int trial = 0; trial < 100; trial++) {
            int n = 2 + random.nextInt(6);
            List<Destination> points = new ArrayList<>(); points.add(depot());
            for (int i = 1; i < n; i++) {
                double open = random.nextDouble() * 30;
                points.add(d(i + 1, random.nextDouble() * .1, random.nextDouble() * .1,
                        open, open + random.nextDouble() * 40));
            }
            var g = new DestinationGraph(points, 40);
            double start = trial % 4 == 0 ? 3.5 : 0, period = random.nextDouble() * 80;
            Score expected = oracle(g, new ArrayList<>(), new boolean[n], start, period);
            var exact = new BranchAndBoundSolver().solve(g, start, period, OPTIONS);
            check(exact.status() == OPTIMAL, "Exact search completes");
            check(exact.visitedCount() == expected.count(), "Independent maximum count");
            near(exact.schedule().distanceKm(), expected.distance(), "Independent distance tiebreak");
            validate(g, exact, start, period);
            var greedy = new GreedyInsertionSolver().solve(g, start, period, OPTIONS);
            check(greedy.status() == FEASIBLE_HEURISTIC, "Greedy normal termination");
            check(greedy.visitedCount() <= expected.count(), "Heuristic cannot exceed optimum");
            if (greedy.visitedCount() == expected.count())
                check(greedy.schedule().distanceKm() + 1e-7 >= expected.distance(), "Heuristic distance bound at equal count");
            validate(g, greedy, start, period);
            var nearest = new NearestNeighbourSolver().solve(g, start, period, OPTIONS);
            validate(g, nearest, start, period);
            check(nearest.status() == FEASIBLE_HEURISTIC && nearest.visitedCount() <= expected.count(), "Baseline versus oracle");
            if (nearest.visitedCount() == expected.count())
                check(nearest.schedule().distanceKm() + 1e-7 >= expected.distance(), "Baseline equal-count distance bound");
        }
    }
    /** Enumerates all ordered subsets, including empty; no production scheduler or pruning. */
    private static Score oracle(DestinationGraph g, List<Integer> route, boolean[] used, double start, double period) {
        double time = start, distance = 0; int prev = 0; boolean feasible = true;
        for (int v : route) {
            time = Math.max(time + g.travelMinutes(prev, v), g.destination(v).opensAt());
            if (time > g.destination(v).closesAt() + 1e-9) feasible = false;
            distance += g.distance(prev, v); prev = v;
        }
        time += g.travelMinutes(prev, 0); distance += g.distance(prev, 0);
        Score best = feasible && time <= start + period + 1e-9 ? new Score(route.size(), distance) : new Score(-1, Double.POSITIVE_INFINITY);
        for (int v = 1; v < g.size(); v++) if (!used[v]) {
            used[v] = true; route.add(v);
            Score candidate = oracle(g, route, used, start, period);
            route.remove(route.size() - 1); used[v] = false;
            if (candidate.count() > best.count() || (candidate.count() == best.count() && candidate.distance() < best.distance())) best = candidate;
        }
        return best;
    }
    private static void validate(DestinationGraph g, RouteResult result, double start, double period) {
        check(result.hasRoute(), "Feasible route retained"); var s = result.schedule();
        check(s.route().get(0) == 0 && s.route().get(s.route().size() - 1) == 0, "Closed route");
        Set<Integer> seen = new HashSet<>();
        double time = start, distance = 0, travel = 0, waiting = 0;
        for (int i = 1; i < s.route().size(); i++) {
            int a = s.route().get(i - 1), b = s.route().get(i);
            if (i < s.route().size() - 1) check(b != 0 && seen.add(b), "Unique customers");
            Destination x = g.destination(a), y = g.destination(b);
            double lat1 = Math.toRadians(x.latitude()), lat2 = Math.toRadians(y.latitude());
            double h = Math.pow(Math.sin((lat2 - lat1) / 2), 2)
                    + Math.cos(lat1) * Math.cos(lat2) * Math.pow(Math.sin(Math.toRadians(y.longitude() - x.longitude()) / 2), 2);
            double km = 2 * 6371.0088 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
            near(g.distance(a, b), km, "Independent Haversine distance");
            double arrival = time + g.travelMinutes(a, b), visit = b == 0 ? arrival : Math.max(arrival, y.opensAt());
            if (b != 0) check(visit <= y.closesAt() + 1e-7, "Window met");
            near(s.visits().get(i).arrival(), arrival, "Arrival"); near(s.visits().get(i).visitTime(), visit, "Visit");
            near(s.visits().get(i).waiting(), visit - arrival, "Waiting");
            distance += km; travel += g.travelMinutes(a, b); waiting += visit - arrival; time = visit;
        }
        check(result.visitedCount() == seen.size(), "Depot excluded from count");
        check(time <= start + period + 1e-7, "Return within period");
        near(s.distanceKm(), distance, "Distance"); near(s.travelMinutes(), travel, "Travel");
        near(s.waitingMinutes(), waiting, "Total waiting"); near(s.finishTime(), time, "Finish");
        near(time - start, travel + waiting, "Zero service duration");
    }
    private static void scenariosAndCli() throws Exception {
        Path tmp = Files.createTempDirectory("route-tests-");
        try {
            Path rows = tmp.resolve("places.txt");
            String row = "1\tPlace\tPlace\t\t0\t0\tP\tPPL\tMY\t\t14\t\t\t\t0\t\t0\tAsia/Kuala_Lumpur\t2020-01-01";
            Files.writeString(rows, row + "\n");
            check(GeoNamesLoader.loadSelected(rows, Set.of(1L)).get(1L).admin1().equals("14"), "Empty columns preserved");
            rejects(() -> GeoNamesLoader.loadSelected(rows, Set.of(2L)));
            Files.writeString(rows, row + "\n" + row + "\n"); rejects(() -> GeoNamesLoader.loadSelected(rows, Set.of(1L)));
            Files.writeString(rows, row.replace("\t0\t0\tP", "\t91\t0\tP")); rejects(() -> GeoNamesLoader.loadSelected(rows, Set.of(1L)));
            Files.writeString(rows, "1\tPlace\n"); rejects(() -> GeoNamesLoader.loadSelected(rows, Set.of(1L)));
            // Synthetic full-source fixture: correctness tests do not depend on the user's current data/.
            StringBuilder sourceRows = new StringBuilder(sourceRow(1735161L, 0, "P", "14", 10000));
            for (int i = 1; i <= 30; i++)
                sourceRows.append(sourceRow(2000000L + i, i, i % 3 == 0 ? "S" : "P", i <= 20 ? "14" : "02", i * 100));
            Path source = tmp.resolve("MY.txt"); Files.writeString(source, sourceRows);
            String originalSource = Files.readString(source);
            Path generated = tmp.resolve("generated");
            var defaults = GenerationOptions.defaults();
            ScenarioFiles.generate(source, generated, defaults);
            var demo = ScenarioFiles.load(generated, null);
            near(demo.durationMinutes(), 120, "Configured period");
            check(demo.graph().size() == 10 && demo.graph().destination(0).geoNameId() == 1735161L, "Variable generator defaults");
            check(demo.graph().destination(1).geoNameId() == 2000020L, "Highest population selected first");
            List<Integer> route = Arrays.stream(Files.readAllLines(generated.resolve("reference-tour.txt")).get(1).split(" -> "))
                    .map(Long::parseLong).map(demo.graph()::indexOf).toList();
            check(ScheduleEvaluator.evaluate(demo.graph(), route, 0, 10000).feasible(), "Generated witness fits windows");
            var greedy = new GreedyInsertionSolver().solve(demo.graph(), 0, 120, OPTIONS);
            var exact = new BranchAndBoundSolver().solve(demo.graph(), 0, 120, OPTIONS);
            validate(demo.graph(), greedy, 0, 120); validate(demo.graph(), exact, 0, 120);
            check(exact.status() == OPTIMAL && exact.visitedCount() >= greedy.visitedCount(), "Generated objective");
            var slower = ScenarioFiles.load(generated, 20.0);
            near(slower.graph().travelMinutes(0, 1), 2 * demo.graph().travelMinutes(0, 1), "Speed override");
            String windows = Files.readString(generated.resolve("windows.tsv"));
            ScenarioFiles.generate(source, generated, defaults);
            check(Files.readString(generated.resolve("windows.tsv")).equals(windows), "Reproducible in-place regeneration");
            var randomSelection = new GeoNamesLoader.Selection(6, "P", "all", 1735161L, "random", 91);
            var randomOptions = new GenerationOptions(randomSelection, 30, "09:00", 180, 15);
            ScenarioFiles.generate(source, generated, randomOptions);
            var randomized = ScenarioFiles.load(generated, null);
            check(randomized.graph().size() == 6, "In-place overwrite changes count");
            near(randomized.speedKmh(), 30, "Generated speed"); near(randomized.durationMinutes(), 180, "Generated duration");
            check(randomized.clockStartMinutes() == 540, "Generated clock");
            windows = Files.readString(generated.resolve("windows.tsv"));
            ScenarioFiles.generate(source, generated, randomOptions);
            check(Files.readString(generated.resolve("windows.tsv")).equals(windows), "Same random seed reproduces selection/windows");
            var changedSeed = new GenerationOptions(new GeoNamesLoader.Selection(6, "P", "all", 1735161L, "random", 92), 30, "09:00", 180, 15);
            ScenarioFiles.generate(source, generated, changedSeed);
            check(!Files.readString(generated.resolve("windows.tsv")).equals(windows), "Different seed changes scenario");
            var filtered = new GeoNamesLoader.Selection(4, "S", "02", 1735161L, "population", 42);
            for (var place : GeoNamesLoader.select(source, filtered).subList(1, 4))
                check(place.featureClass().equals("S") && place.admin1().equals("02"), "Customer filters; depot bypasses filter");
            var customDepot = new GeoNamesLoader.Selection(4, "all", "all", 2000001L, "population", 42);
            check(GeoNamesLoader.select(source, customDepot).get(0).id() == 2000001L, "Custom depot");
            var onlyDepot = new GenerationOptions(new GeoNamesLoader.Selection(1, "P", "14", 1735161L, "population", 42), 40, "08:00", 0, 0);
            ScenarioFiles.generate(source, generated, onlyDepot);
            check(ScenarioFiles.load(generated, null).graph().size() == 1, "Depot-only generation");
            String preserved = Files.readString(generated.resolve("windows.tsv"));
            rejects(() -> ScenarioFiles.generate(source, generated,
                    new GenerationOptions(new GeoNamesLoader.Selection(100, "P", "14", 1735161L, "population", 42), 40, "08:00", 120, 30)));
            check(Files.readString(generated.resolve("windows.tsv")).equals(preserved), "Impossible selection leaves scenario unchanged");
            rejects(() -> GeoNamesLoader.select(source, new GeoNamesLoader.Selection(2, "P", "14", 999L, "population", 42)));
            rejects(() -> new GeoNamesLoader.Selection(0, "P", "14", 1735161L, "population", 42));
            rejects(() -> new GeoNamesLoader.Selection(2, "X", "14", 1735161L, "population", 42));
            rejects(() -> new GeoNamesLoader.Selection(2, "P", "14", 1735161L, "wrong", 42));
            rejects(() -> new GenerationOptions(randomSelection, 0, "08:00", 120, 30));
            rejects(() -> new GenerationOptions(randomSelection, 40, "25:00", 120, 30));
            rejects(() -> new GenerationOptions(randomSelection, 40, "08:00", 120, -1));
            rejects(() -> ScenarioFiles.generate(generated.resolve("destinations.txt"), generated, onlyDepot));
            check(Files.readString(source).equals(originalSource), "Original MY.txt is unchanged");
            ScenarioFiles.generate(source, generated, defaults);
            cli(generated, "09:00", "30", 0, "Departure: 09:00:00; period: 30.000 min; return by: 09:30:00");
            cli(generated, "0", "0", 0, "Visited: 0/9 customers");
            cli(generated, "07:00", "30", 1, "precedes the window origin");
            cli(generated, "08:00", "-1", 1, "Time period must be");
            // Exercise the public CLI twice to prove it replaces data/ rather than requiring a new folder.
            generationCli(tmp, source, "5", 0);
            check(ScenarioFiles.load(tmp.resolve("data"), null).graph().size() == 5, "CLI generates requested count");
            generationCli(tmp, source, "7", 0);
            check(ScenarioFiles.load(tmp.resolve("data"), null).graph().size() == 7, "CLI replaces data/ in place");
            generationCli(tmp, source, "999", 1);
            check(ScenarioFiles.load(tmp.resolve("data"), null).graph().size() == 7, "Failed CLI preserves previous scenario");
            Files.writeString(generated.resolve("windows.tsv"), "geonameid\topensAt\tclosesAt\n1735161\t\t10\n");
            rejects(() -> ScenarioFiles.load(generated, null));
            Files.writeString(generated.resolve("windows.tsv"), "geonameid\topensAt\tclosesAt\n1735161\t20\t10\n");
            rejects(() -> ScenarioFiles.load(generated, null));
            Files.writeString(generated.resolve("windows.tsv"), "geonameid\topensAt\tclosesAt\n1735161\t0\t10\n1735161\t0\t10\n");
            rejects(() -> ScenarioFiles.load(generated, null));
        } finally {
            try (var paths = Files.walk(tmp)) {
                for (Path path : paths.sorted(Comparator.reverseOrder()).toList()) Files.delete(path);
            }
        }
    }
    private static String sourceRow(long id, int offset, String featureClass, String admin1, long population) {
        String[] fields = new String[19]; Arrays.fill(fields, "");
        fields[0] = Long.toString(id); fields[1] = "Synthetic " + id; fields[2] = fields[1];
        fields[4] = Double.toString(3 + offset * .002); fields[5] = Double.toString(101 + offset * .003);
        fields[6] = featureClass; fields[7] = "PPL"; fields[8] = "MY"; fields[10] = admin1;
        fields[14] = Long.toString(population); fields[18] = "2020-01-01";
        return String.join("\t", fields) + "\n";
    }
    private static void generationCli(Path working, Path source, String count, int expectedExit) throws Exception {
        String javaExecutable = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        Process process = new ProcessBuilder(javaExecutable, "-cp", Path.of("out").toAbsolutePath().toString(),
                "app.Main", "--generate", source.toString(), "--count", count, "--selection", "random", "--seed", "19")
                .directory(working.toFile()).redirectErrorStream(true).start();
        String text = new String(process.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        check(process.waitFor() == expectedExit, "Generation CLI: " + text);
    }
    private static void cli(Path scenario, String start, String period, int expectedExit, String expectedText) throws Exception {
        String javaExecutable = Path.of(System.getProperty("java.home"), "bin", "java").toString();
        Process process = new ProcessBuilder(javaExecutable, "-cp", "out", "app.Main", "--data", scenario.toString(), "--algorithm", "exact",
                "--start-time", start, "--duration-minutes", period).redirectErrorStream(true).start();
        String text = new String(process.getInputStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        check(process.waitFor() == expectedExit && text.contains(expectedText), "CLI: " + start + ", " + period + ": " + text);
    }
}
