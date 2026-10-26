package graph;

import java.util.*;

/** Complete symmetric graph of selected locations only. Vertex zero is the depot. */
public final class DestinationGraph {
    private final List<Destination> destinations;
    private final Map<Long, Integer> indices = new HashMap<>();
    private final double[][] distances, travelMinutes;

    public DestinationGraph(List<Destination> destinations, double speedKmh) {
        if (destinations == null || destinations.isEmpty())
            throw new IllegalArgumentException("A depot is required");
        if (!Double.isFinite(speedKmh) || speedKmh <= 0)
            throw new IllegalArgumentException("Speed must be positive and finite");
        this.destinations = List.copyOf(destinations);
        int n = destinations.size();
        distances = new double[n][n];
        travelMinutes = new double[n][n];
        for (int i = 0; i < n; i++) {
            if (indices.put(destinations.get(i).geoNameId(), i) != null)
                throw new IllegalArgumentException("Duplicate GeoNameID: " + destinations.get(i).geoNameId());
            for (int j = 0; j < i; j++) {
                double km = haversine(destinations.get(i), destinations.get(j));
                double minutes = km * 60.0 / speedKmh;
                if (!Double.isFinite(minutes)) throw new IllegalArgumentException("Travel time overflow");
                distances[i][j] = distances[j][i] = km;
                travelMinutes[i][j] = travelMinutes[j][i] = minutes;
            }
        }
    }

    public int size() { return destinations.size(); }
    public Destination destination(int index) { return destinations.get(index); }
    public List<Destination> destinations() { return destinations; }
    public int indexOf(long id) {
        Integer index = indices.get(id);
        if (index == null) throw new IllegalArgumentException("Unknown GeoNameID: " + id);
        return index;
    }
    public double distance(int from, int to) { return distances[from][to]; }
    public double travelMinutes(int from, int to) { return travelMinutes[from][to]; }

    public static double haversine(Destination a, Destination b) {
        double lat = Math.toRadians(b.latitude() - a.latitude());
        double lon = Math.toRadians(b.longitude() - a.longitude());
        double h = Math.sin(lat / 2) * Math.sin(lat / 2)
                + Math.cos(Math.toRadians(a.latitude())) * Math.cos(Math.toRadians(b.latitude()))
                * Math.sin(lon / 2) * Math.sin(lon / 2);
        return 6371.0088 * 2 * Math.asin(Math.sqrt(Math.max(0, Math.min(1, h))));
    }
}
