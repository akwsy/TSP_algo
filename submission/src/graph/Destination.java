package graph;

/** One geographic location. Windows are minutes relative to the scenario start. */
public record Destination(long geoNameId, String name, double latitude, double longitude,
                          double opensAt, double closesAt) {
    public Destination {
        if (geoNameId <= 0 || name == null || name.isBlank())
            throw new IllegalArgumentException("Destination needs a positive ID and name");
        if (!Double.isFinite(latitude) || latitude < -90 || latitude > 90
                || !Double.isFinite(longitude) || longitude < -180 || longitude > 180)
            throw new IllegalArgumentException("Invalid coordinates for " + geoNameId);
        if (!Double.isFinite(opensAt) || !Double.isFinite(closesAt) || opensAt < 0 || closesAt < opensAt)
            throw new IllegalArgumentException("Invalid/missing time window for " + geoNameId);
    }
}
