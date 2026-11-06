package app;

import graph.GeoNamesLoader.Selection;

/** Reproducible selection and simulated-scenario settings. */
public record GenerationOptions(Selection selection, double speedKmh, String startClock,
                                double durationMinutes, double windowSlackMinutes, String windowMode) {
    public static final String SLACK = "slack", BLOCKS = "blocks";
    /** Slack-mode options (the default window mode). */
    public GenerationOptions(Selection selection, double speedKmh, String startClock,
                             double durationMinutes, double windowSlackMinutes) {
        this(selection, speedKmh, startClock, durationMinutes, windowSlackMinutes, SLACK);
    }
    public GenerationOptions {
        if (selection == null) throw new IllegalArgumentException("Selection is required");
        if (!Double.isFinite(speedKmh) || speedKmh <= 0 || !Double.isFinite(durationMinutes)
                || durationMinutes < 0 || !Double.isFinite(windowSlackMinutes) || windowSlackMinutes < 0)
            throw new IllegalArgumentException("Invalid speed, duration or window slack");
        if (startClock == null || !startClock.matches("(?:[01][0-9]|2[0-3]):[0-5][0-9]"))
            throw new IllegalArgumentException("Start clock must be HH:mm");
        requireWindowMode(windowMode);
    }
    public static void requireWindowMode(String mode) {
        if (!SLACK.equals(mode) && !BLOCKS.equals(mode))
            throw new IllegalArgumentException("Window mode must be slack or blocks");
    }
    public static GenerationOptions defaults() {
        return new GenerationOptions(Selection.defaults(), 40, "08:00", 120, 30);
    }
}
