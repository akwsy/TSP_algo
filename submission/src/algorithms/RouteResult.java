package algorithms;

/** Every result includes a feasible closed route, possibly visiting zero customers. */
public record RouteResult(Status status, ScheduleEvaluator.Schedule schedule,
                          double elapsedMillis, long exploredStates, String message) {
    public enum Status { FEASIBLE_HEURISTIC, OPTIMAL, SEARCH_LIMIT_REACHED }
    public static RouteResult of(Status status, ScheduleEvaluator.Schedule schedule,
                                 long startedNanos, long states, String message) {
        return new RouteResult(status, schedule, (System.nanoTime() - startedNanos) / 1_000_000.0, states, message);
    }
    public boolean hasRoute() { return schedule != null; }
    public int visitedCount() { return schedule == null ? 0 : schedule.route().size() - 2; }
}
