package graph;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.function.Consumer;

/** Reads UTF-8 GeoNames TSV, preserving empty fields and validating every row. */
public final class GeoNamesLoader {
    private GeoNamesLoader() {}

    public record Place(long id, String name, double latitude, double longitude,
                        String featureClass, String admin1, long population, String rawLine) {
        public Destination withWindow(double open, double close) {
            return new Destination(id, name, latitude, longitude, open, close);
        }
    }

    private static void read(Path path, Consumer<Place> accept) throws IOException {
        Set<Long> seen = new HashSet<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            int lineNumber = 0;
            while ((line = reader.readLine()) != null) {
                lineNumber++;
                if (line.isBlank()) continue;
                try {
                    String[] f = line.split("\t", -1);
                    if (f.length != 19) throw new IllegalArgumentException("Expected 19 columns");
                    long id = Long.parseLong(f[0]);
                    double lat = Double.parseDouble(f[4]), lon = Double.parseDouble(f[5]);
                    new Destination(id, f[1], lat, lon, 0, Double.MAX_VALUE);
                    if (!seen.add(id)) throw new IllegalArgumentException("Duplicate ID " + id);
                    long population = Long.parseLong(f[14]);
                    if (population < 0 || f[6].isBlank() || f[8].isBlank())
                        throw new IllegalArgumentException("Invalid population or missing classification/country");
                    accept.accept(new Place(id, f[1], lat, lon, f[6], f[10], population, line));
                } catch (IllegalArgumentException e) {
                    throw new IOException(path + ": line " + lineNumber + ": " + e.getMessage(), e);
                }
            }
        }
    }

    /** Count includes the depot. Filters apply to customers, not the explicit depot. */
    public record Selection(int count, String featureClass, String admin1, long depotId,
                            String method, long seed) {
        public Selection {
            if (count < 1 || depotId < 1) throw new IllegalArgumentException("Count and depot ID must be positive");
            if (featureClass == null || !(featureClass.equals("all") || featureClass.matches("[AHLPRSTUV]")))
                throw new IllegalArgumentException("Feature class must be A/H/L/P/R/S/T/U/V or all");
            if (admin1 == null || admin1.isBlank()) throw new IllegalArgumentException("Admin1 code is required (or all)");
            if (!Set.of("population", "random").contains(method))
                throw new IllegalArgumentException("Selection must be population or random");
        }
        public static Selection defaults() { return new Selection(10, "P", "14", 1735161L, "population", 42); }
    }

    public static List<Place> select(Path path, Selection selection) throws IOException {
        List<Place> candidates = new ArrayList<>();
        Place[] depot = new Place[1];
        read(path, p -> {
            if (p.id() == selection.depotId()) depot[0] = p;
            else if ((selection.featureClass().equals("all") || p.featureClass().equals(selection.featureClass()))
                    && (selection.admin1().equals("all") || p.admin1().equals(selection.admin1()))) candidates.add(p);
        });
        if (depot[0] == null) throw new IOException("Depot ID not found: " + selection.depotId());
        if (candidates.size() < selection.count() - 1)
            throw new IOException("Requested " + selection.count() + " destinations including depot, but only "
                    + (candidates.size() + 1) + " satisfy the selection");
        if (selection.method().equals("population"))
            candidates.sort(Comparator.comparingLong(Place::population).reversed().thenComparingLong(Place::id));
        else {
            candidates.sort(Comparator.comparingLong(Place::id));
            Collections.shuffle(candidates, new Random(selection.seed()));
        }
        List<Place> selected = new ArrayList<>(); selected.add(depot[0]);
        selected.addAll(candidates.subList(0, selection.count() - 1));
        return List.copyOf(selected);
    }

    public static Map<Long, Place> loadSelected(Path path, Set<Long> ids) throws IOException {
        Map<Long, Place> result = new HashMap<>();
        read(path, p -> { if (ids.contains(p.id())) result.put(p.id(), p); });
        if (!result.keySet().equals(ids)) {
            Set<Long> missing = new TreeSet<>(ids); missing.removeAll(result.keySet());
            throw new IOException("Missing GeoNameIDs: " + missing);
        }
        return Map.copyOf(result);
    }
}
