package algorithms;

import graph.DestinationGraph;

public interface RouteSolver {
    RouteResult solve(DestinationGraph graph, double startTime, double timePeriod, SolverOptions options);
}
