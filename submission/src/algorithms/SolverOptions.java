package algorithms;

import java.util.concurrent.TimeUnit;

public record SolverOptions(int maxDestinations, long timeLimitMillis) {
    public SolverOptions {
        if (maxDestinations < 1 || timeLimitMillis < 0)
            throw new IllegalArgumentException("Invalid solver limits");
    }
    public static SolverOptions defaults() { return new SolverOptions(15, 10_000); }
    boolean expired(long started) {
        return System.nanoTime() - started >= TimeUnit.MILLISECONDS.toNanos(timeLimitMillis);
    }
}
