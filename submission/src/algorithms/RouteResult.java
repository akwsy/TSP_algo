package algorithms;

/** Every result includes a feasible closed route, possibly visiting zero customers. */
public record RouteResult(Status status, ScheduleEvaluator.Schedule schedule,
                          double elapsedMillis, long exploredStates, String message) {
    public enum Status { FEASIBLE_HEURISTIC, OPTIMAL, SEARCH_LIMIT_REACHED }
    public boolean hasRoute() { return schedule != null; }
    public int visitedCount() { return schedule == null ? 0 : schedule.route().size() - 2; }
}
