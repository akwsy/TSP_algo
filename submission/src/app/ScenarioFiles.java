package app;

import graph.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Editable scenario format, independent of the original full dataset after generation. */
public final class ScenarioFiles {
    private ScenarioFiles() {}
    public record Scenario(DestinationGraph graph, int clockStartMinutes, double speedKmh, double durationMinutes) {}

    public static Scenario load(Path dir, Double speedOverride) throws IOException {
        Properties config = new Properties();
        try (Reader reader = Files.newBufferedReader(dir.resolve("scenario.properties"), StandardCharsets.UTF_8)) {
            config.load(reader);
        }
        try {
            double speed = speedOverride == null ? Double.parseDouble(config.getProperty("speedKmh", "40")) : speedOverride;
            String[] clock = config.getProperty("startClock", "08:00").split(":", -1);
            if (clock.length != 2) throw new IllegalArgumentException("startClock must be HH:mm");
            int hour = Integer.parseInt(clock[0]), minute = Integer.parseInt(clock[1]);
            if (hour < 0 || hour > 23 || minute < 0 || minute > 59) throw new IllegalArgumentException("Invalid startClock");
            List<Long> order = new ArrayList<>();
            Map<Long, double[]> windows = new LinkedHashMap<>();
            List<String> lines = Files.readAllLines(dir.resolve("windows.tsv"), StandardCharsets.UTF_8);
            if (lines.isEmpty() || !lines.get(0).equals("geonameid\topensAt\tclosesAt"))
                throw new IllegalArgumentException("Invalid windows.tsv header");
            for (int i = 1; i < lines.size(); i++) {
                if (lines.get(i).isBlank()) continue;
                String[] fields = lines.get(i).split("\t", -1);
                if (fields.length != 3 || fields[1].isBlank() || fields[2].isBlank())
                    throw new IllegalArgumentException("Missing/invalid window on line " + (i + 1));
                long id = Long.parseLong(fields[0]);
                double[] window = { Double.parseDouble(fields[1]), Double.parseDouble(fields[2]) };
                if (windows.put(id, window) != null) throw new IllegalArgumentException("Duplicate window ID " + id);
                order.add(id);
            }
            if (order.isEmpty()) throw new IllegalArgumentException("Scenario needs a depot row");
            Map<Long, GeoNamesLoader.Place> places = GeoNamesLoader.loadSelected(dir.resolve("destinations.txt"), windows.keySet());
            List<Destination> destinations = new ArrayList<>();
            for (long id : order) {
                double[] window = windows.get(id);
                destinations.add(places.get(id).withWindow(window[0], window[1]));
            }
            double duration = Double.parseDouble(config.getProperty("durationMinutes", "120"));
            if (!Double.isFinite(duration) || duration < 0) throw new IllegalArgumentException("Invalid durationMinutes");
            return new Scenario(new DestinationGraph(destinations, speed), hour * 60 + minute, speed, duration);
        } catch (IllegalArgumentException e) {
            throw new IOException("Invalid scenario: " + e.getMessage(), e);
        }
    }

    /** Replace this scenario's five generated files after fully validating and staging the new data. */
    public static void generate(Path source, Path output, GenerationOptions options) throws IOException {
        String[] names = {"destinations.txt", "windows.tsv", "scenario.properties", "reference-tour.txt", "DATA_NOTES.md"};
        for (String name : names) {
            Path target = output.resolve(name);
            if (source.toAbsolutePath().normalize().equals(target.toAbsolutePath().normalize())
                    || (Files.exists(target) && Files.isSameFile(source, target)))
                throw new IOException("The GeoNames source must not be one of the scenario output files");
            if (Files.exists(target) && !Files.isRegularFile(target))
                throw new IOException("Scenario output is not a regular file: " + name);
        }
        var selection = options.selection();
        List<GeoNamesLoader.Place> places = GeoNamesLoader.select(source, selection);
        List<Destination> unbounded = places.stream().map(p -> p.withWindow(0, Double.MAX_VALUE)).toList();
        List<Integer> reference = new ArrayList<>();
        for (int i = 1; i < places.size(); i++) reference.add(i);
        Collections.shuffle(reference, new Random(selection.seed()));
        double[] open = new double[places.size()], close = new double[places.size()];
        close[0] = Double.MAX_VALUE;
        double time = 0; int previous = 0;
        for (int v : reference) {
            time += DestinationGraph.haversine(unbounded.get(previous), unbounded.get(v)) * 60 / options.speedKmh();
            open[v] = Math.max(0, time - options.windowSlackMinutes());
            close[v] = time + options.windowSlackMinutes();
            if (!Double.isFinite(close[v])) throw new IOException("Generated time window overflow");
            previous = v;
        }
        StringBuilder rows = new StringBuilder(), windows = new StringBuilder("geonameid\topensAt\tclosesAt\n");
        for (int i = 0; i < places.size(); i++) {
            rows.append(places.get(i).rawLine()).append('\n');
            windows.append(places.get(i).id()).append('\t').append(open[i]).append('\t').append(close[i]).append('\n');
        }
        StringBuilder tour = new StringBuilder("# Generation witness only; neither solver reads this file.\n");
        tour.append(places.get(0).id());
        for (int v : reference) tour.append(" -> ").append(places.get(v).id());
        tour.append(" -> ").append(places.get(0).id()).append('\n');
        String properties = "# Travel times and windows are SIMULATED.\n"
                + "speedKmh=" + options.speedKmh() + "\nstartClock=" + options.startClock()
                + "\ndurationMinutes=" + options.durationMinutes()
                + "\nselectionCount=" + selection.count() + "\nselectionFeatureClass=" + selection.featureClass()
                + "\nselectionAdmin1=" + selection.admin1() + "\nselectionDepotId=" + selection.depotId()
                + "\nselectionMethod=" + selection.method() + "\nselectionSeed=" + selection.seed()
                + "\nwindowSlackMinutes=" + options.windowSlackMinutes() + "\n";
        String notes = """
                # Generated scenario data

                Geographic source: supplied GeoNames MY.txt. Original rows retain all 19 columns.
                https://www.geonames.org/ ; source metadata states CC BY 4.0:
                https://creativecommons.org/licenses/by/4.0/
                Geographic records are supplied as-is, without accuracy guarantees.

                """ + "Selection: " + selection.count() + " vertices including depot " + selection.depotId()
                + "; " + (selection.count() - 1) + " potential customers.\n"
                + "Customer filters: feature class " + selection.featureClass() + ", admin1 " + selection.admin1() + ".\n"
                + "Method: " + selection.method() + "; seed " + selection.seed() + ". The explicit depot bypasses customer filters.\n"
                + "Population selection sorts by descending population, then ID; random selection shuffles ID-sorted candidates.\n"
                + "Selection settings are recorded in scenario.properties. No source-device path is stored.\n\n"
                + "SIMULATION: Haversine distances, Earth radius 6371.0088 km; constant " + options.speedKmh()
                + " km/h; origin " + options.startClock() + "; zero service time.\n"
                + "Windows use a shuffled reference route with the same seed and +/-" + options.windowSlackMinutes()
                + " minutes slack (openings clipped to zero). They are not real appointments.\n"
                + "The reference witness satisfies customer windows but may exceed the period. Neither solver reads it.\n"
                + "Trip period: " + options.durationMinutes() + " minutes including waiting and return.\n"
                + "Maximize customer visits; shorter distance breaks equal-count ties.\n"
                + "Regeneration replaces these scenario files and resets their settings/windows to the command's options.\n";
        Map<String, String> contents = new LinkedHashMap<>();
        contents.put(names[0], rows.toString()); contents.put(names[1], windows.toString());
        contents.put(names[2], properties); contents.put(names[3], tour.toString()); contents.put(names[4], notes);
        replaceScenario(output, contents);
    }

    private static void replaceScenario(Path output, Map<String, String> contents) throws IOException {
        Files.createDirectories(output);
        Path staged = Files.createTempDirectory(output, ".generation-");
        Map<String, byte[]> originals = new LinkedHashMap<>();
        List<String> replaced = new ArrayList<>();
        try {
            for (var entry : contents.entrySet()) {
                Path target = output.resolve(entry.getKey());
                originals.put(entry.getKey(), Files.exists(target) ? Files.readAllBytes(target) : null);
                Files.writeString(staged.resolve(entry.getKey()), entry.getValue(), StandardCharsets.UTF_8);
            }
            for (String name : contents.keySet()) {
                Files.move(staged.resolve(name), output.resolve(name), StandardCopyOption.REPLACE_EXISTING);
                replaced.add(name);
            }
        } catch (IOException failure) {
            // Restore the previous scenario if a normal replacement operation fails.
            for (String name : replaced) try {
                byte[] original = originals.get(name);
                if (original == null) Files.deleteIfExists(output.resolve(name));
                else Files.write(output.resolve(name), original);
            } catch (IOException restoreFailure) { failure.addSuppressed(restoreFailure); }
            throw failure;
        } finally {
            try (var files = Files.list(staged)) {
                for (Path file : files.toList()) Files.deleteIfExists(file);
            }
            Files.deleteIfExists(staged);
        }
    }
}
