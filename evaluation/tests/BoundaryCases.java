package tests;

import algorithms.*;
import evaluation.algorithms.NearestNeighbourSolver;
import graph.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/**
 * Hand-built boundary scenarios. Every expected value is a literal derived by hand; nothing is
 * recomputed with the solvers.
 *
 * Geometry: all points lie on the equator (the longitude in degrees is the 1-D coordinate "x";
 * the depot is x = 0). The speed is {@link #KM_PER_DEG} km/h, so exactly 1 degree of longitude
 * takes 60 minutes, and the distance between x1 and x2 is |x1 - x2| degrees (expectations are
 * therefore written in degrees and converted to km only for the comparison). The departure is
 * always time 0 and windows are minutes relative to it.
 *
 * Deadline and window comparisons in the solvers carry a 1e-9 tolerance, so "exactly at the
 * boundary" cases are robust to floating-point noise of order 1e-13.
 *
 * Expected values are given per algorithm. Where the heuristics fall short of the exact optimum,
 * the case comment explains why and the shortfall is asserted so the weakness stays documented.
 * Usage: BoundaryCases [--emit file.json]
 */
public final class BoundaryCases {
    /** Kilometres in one degree of equatorial arc: 6371.0088 km * pi / 180. */
    static final double KM_PER_DEG = 111.1950802335329;
    static final double MAX = Double.MAX_VALUE;

    /** Expected outcome: number of customers visited and total tour length in degrees. */
    record Exp(int visits, double deg) {}
    record Case(String name, String description, double period, List<Destination> places,
                Exp nearest, Exp greedy, Exp exact) {}

    static Destination depot() { return at(1, 0, 0, MAX); }
    static Destination at(long id, double x, double open, double close) {
        return new Destination(id, "Place " + id, 0, x, open, close);
    }
    static Destination open(long id, double x) { return at(id, x, 0, 1000); }
    static Case c(String name, String description, double period, List<Destination> customers,
                  Exp nearest, Exp greedy, Exp exact) {
        List<Destination> all = new ArrayList<>(); all.add(depot()); all.addAll(customers);
        return new Case(name, description, period, all, nearest, greedy, exact);
    }
    static Exp e(int visits, double deg) { return new Exp(visits, deg); }

    static List<Case> cases() {
        List<Case> cs = new ArrayList<>();

        // 1. Only open location is far away. A(0.5), B(1.0), D(4.0) close at t=10 but cannot be
        // reached before t=30, so they are unreachable. C at x=3 opens at 100 and is reached at 180,
        // the visit starts at 180, return at 360 <= 400. One visit, tour 2*3 = 6 deg.
        cs.add(c("far-only-open", "Only the farthest location is open; near ones are closed on arrival. Period 400 reaches it (return at 360).",
                400, List.of(at(2, .5, 0, 10), at(3, 1, 0, 10), at(4, 3, 100, 1000), at(5, 4, 0, 10)),
                e(1, 6), e(1, 6), e(1, 6)));
        // Same with period 359: return 360 > 359, nothing fits, depot-only route.
        cs.add(c("far-only-open-too-short", "Same layout, period 359 is one minute short of the 360-minute return.",
                359, List.of(at(2, .5, 0, 10), at(3, 1, 0, 10), at(4, 3, 100, 1000), at(5, 4, 0, 10)),
                e(0, 0), e(0, 0), e(0, 0)));

        // 2. Deadline. Round trip to x=1 is 120 min = the period (back exactly at the deadline).
        // B at x=-1.001 needs 120.12 min, 0.12 beyond the period. NN and greedy take A (cost 2 deg).
        cs.add(c("deadline-exact-and-beyond", "A returns exactly at the deadline (120); B would return at 120.12. Only A fits.",
                120, List.of(open(2, 1), open(3, -1.001)), e(1, 2), e(1, 2), e(1, 2)));
        cs.add(c("deadline-just-beyond", "Only B (return at 120.12 > 120) exists: depot-only route.",
                120, List.of(open(2, -1.001)), e(0, 0), e(0, 0), e(0, 0)));

        // 3a. Nearest-neighbour trap through a window. A(-1) is nearest but leads away; B(1.5) closes
        // at t=100. Best: B first (90 <= 100), then A (90+150 = 240), back at 300 = period: 2 visits,
        // tour 1.5 + 2.5 + 1 = 5 deg. NN goes to A first (60), then B would be reached at 210 > 100: 1 visit.
        // Greedy inserts B before A and recovers both visits. NN fails.
        cs.add(c("nn-trap-window", "Nearest customer A first makes B (closes at 100) unreachable; B then A fits exactly in 300.",
                300, List.of(open(2, -1), at(3, 1.5, 0, 100)), e(1, 2), e(2, 5), e(2, 5)));
        // 3b. Nearest-neighbour trap through geometry. A(-1) is nearest; B(1.5), C(2.0), D(2.5) lie on
        // one side. Exact: out to 2.5 and back = 5 deg = 300 min, 3 visits (a tour containing A and any
        // of C, D needs at least 6 deg = 360 > 300; A with B only is 5 deg but just 2 visits).
        // NN: A (60), then B reached at 210 (return at exactly 300), C and D no longer fit: 2 visits, tour
        // 1 + 2.5 + 1.5 = 5 deg. Greedy also starts with A (insertion cost 2 vs 3, 4, 5) and then adds B
        // (cost 3): 2 visits, 5 deg. NN and greedy both fall one visit short.
        cs.add(c("nn-trap-distance", "Closest customer is on the wrong side: exact takes the three on one side, NN and greedy take A then B.",
                300, List.of(open(2, -1), open(3, 1.5), open(4, 2), open(5, 2.5)), e(2, 5), e(2, 5), e(3, 5)));

        // 4. Greedy-insertion trap. A(1.0), B(2.5), C(-1.2), D(3.2); period 390 (6.5 deg).
        // Exact: A,B,D on one side = tour 6.4 deg = 384 <= 390, 3 visits (no other triple fits:
        // {A,B,C} spans -1.2..2.5 => 7.4 deg, the others 8.8; four visits would need 8.8).
        // Greedy: A (cost 2) first; then C costs 2.4 while B costs 3.0, so C is inserted although it
        // spends the budget on the other side; B and D then no longer fit (span 3.7 => 7.4 deg = 444).
        // Greedy ends with {A,C}, tour 4.4 deg, 2 visits. NN: A, then nearest B (1.5), then D (0.7):
        // 3 visits, 6.4 deg. Only greedy fails.
        cs.add(c("greedy-trap", "Cheapest insertions pick the far-left customer C; B and D then no longer fit. Exact and NN visit A,B,D.",
                390, List.of(open(2, 1), open(3, 2.5), open(4, -1.2), open(5, 3.2)), e(3, 6.4), e(2, 4.4), e(3, 6.4)));

        // 5. Waiting trap. A(0.4) opens at 100; B(-0.5), C(-0.8) are open; period 144.
        // Exact: C,B,A (or B,C,A): C at 48, B at 66, A reached at 120 >= 100 so no wait, back at 144: 3 visits,
        // tour 0.8+0.3+0.9+0.4 = 2.4 deg. NN goes to nearest A first (24 min), waits until 100, then B would
        // be reached at 154 and C at 172 (both past the budget): 1 visit, 0.8 deg. Greedy inserts A (cost 0.8),
        // then B before A (cost 1.0), then C (cost 0.6): 3 visits. Only NN fails (waiting wastes the budget).
        cs.add(c("waiting-trap", "Nearest customer A opens at 100: waiting there loses two visits; visiting B and C first is free.",
                144, List.of(at(2, .4, 100, 1000), open(3, -.5), open(4, -.8)), e(1, .8), e(3, 2.4), e(3, 2.4)));

        // 6. Window closing. Customer at x=0.5 reached at minute 30.
        cs.add(c("window-closes-at-arrival", "Window closes at 30, arrival at exactly 30: visited (inclusive).",
                200, List.of(at(2, .5, 0, 30)), e(1, 1), e(1, 1), e(1, 1)));
        cs.add(c("window-closes-just-before", "Window closes at 29.99, arrival at 30: not visited.",
                200, List.of(at(2, .5, 0, 29.99)), e(0, 0), e(0, 0), e(0, 0)));

        // 7. Degenerate instances.
        cs.add(c("all-closed-or-unreachable", "A is closed on arrival (30 > 10), B is 300 min away with period 100: depot-only route is optimal.",
                100, List.of(at(2, .5, 0, 10), open(3, 5)), e(0, 0), e(0, 0), e(0, 0)));
        cs.add(c("zero-period-noncoincident", "Zero period: a customer 30 minutes away cannot be visited.",
                0, List.of(open(2, .5)), e(0, 0), e(0, 0), e(0, 0)));
        cs.add(c("zero-period-coincident", "Zero period: only the customer at the depot's coordinates (window contains departure) fits, distance 0.",
                0, List.of(at(2, 0, 0, 100), open(3, .5)), e(1, 0), e(1, 0), e(1, 0)));
        cs.add(c("single-customer", "One customer 30 minutes away, period exactly 60.",
                60, List.of(open(2, .5)), e(1, 1), e(1, 1), e(1, 1)));

        // 8. Tie-breaks. A(1.0), B(-0.9), C(1.8), period 230: pairs {A,B} = 3.8 deg (228 min) and
        // {A,C} = 3.6 deg (216 min) fit, {B,C} = 5.4 deg and all three do not. Exact: {A,C}, 3.6 deg
        // (equal count 2, shorter distance). NN goes to nearest B (0.9), then A: 3.8 deg. Greedy
        // inserts B first (cost 1.8) then A (cost 2.0; C does not fit): 3.8 deg. Heuristics have the
        // same count but a longer tour.
        cs.add(c("distance-tiebreak", "Two feasible pairs with equal count; the shorter {A,C} wins for exact, NN and greedy pick the longer {A,B}.",
                230, List.of(open(2, 1), open(3, -.9), open(4, 1.8)), e(2, 3.8), e(2, 3.8), e(2, 3.6)));
        // Equal distances: A and B symmetric, only one fits in 120 min. Count 1, tour 2 deg for either choice.
        cs.add(c("equal-distances", "Symmetric customers at +1 and -1, only one fits: tour length 2 deg whichever is chosen.",
                120, List.of(open(2, 1), open(3, -1)), e(1, 2), e(1, 2), e(1, 2)));

        // 9. Identical coordinates and collinear points.
        cs.add(c("identical-coordinates", "Three customers at the same point 30 minutes away: all visited, tour 1 deg.",
                60, List.of(open(2, .5), open(3, .5), open(4, .5)), e(3, 1), e(3, 1), e(3, 1)));
        cs.add(c("identical-coordinates-one-closed", "Two customers at one point, one closed on arrival: exactly one visit.",
                100, List.of(at(2, .5, 0, 10), open(3, .5)), e(1, 1), e(1, 1), e(1, 1)));
        cs.add(c("collinear", "Five collinear customers at 0.2..1.0, period 120 = tour to 1.0 and back: all five, 2 deg.",
                120, List.of(open(2, .2), open(3, .4), open(4, .6), open(5, .8), open(6, 1)), e(5, 2), e(5, 2), e(5, 2)));

        // 10. Four 6-hour clock blocks with an 08:00 start (480 min) and a 1440-minute period.
        // Offsets from the start: 00-06 ends before 08:00 so it moves to the next day: [960,1320];
        // 06-12: open clipped to 0, close 240: [0,240]; 12-18: [240,600]; 18-24: [600,960].
        // K1(id2, x=-0.4, 00-06), K2(id3, x=0.5, 06-12), K3(id4, x=1.0, 12-18), K4(id5, x=-1.0, 18-24).
        // The window order forces K2,K3,K4,K1 (K2 at 30, K3 waits to 240, K4 at 360 waits to 600, K1 at 636
        // waits to 960, back at 984): 4 visits, tour 0.5+0.5+2.0+0.6+0.4 = 4 deg. NN picks the nearest K1
        // first, waits until 960 and loses everything else: 1 visit, 0.8 deg. Greedy inserts K1, then K2
        // before it, then K3, then K4 and reaches the optimum. Only NN fails.
        List<Destination> blocks = List.of(at(2, -.4, 960, 1320), at(3, .5, 0, 240), at(4, 1, 240, 600), at(5, -1, 600, 960));
        cs.add(c("four-blocks-long-period", "Four clock blocks (08:00 start, windows [960,1320],[0,240],[240,600],[600,960]), period 1440: forced order, all four.",
                1440, blocks, e(1, .8), e(4, 4), e(4, 4)));
        // Same blocks, period 300: only K2 then K3 (K3 waits for 240, back at exactly 300). K1, K4 open too late.
        cs.add(c("four-blocks-short-period", "Same blocks with period 300: only the 06-12 and 12-18 customers are reachable (return exactly at 300).",
                300, blocks, e(2, 2), e(2, 2), e(2, 2)));
        return cs;
    }

    record Outcome(int visits, double km, List<Long> route) {}

    static Outcome run(RouteSolver solver, Case cs) {
        DestinationGraph g = new DestinationGraph(cs.places(), KM_PER_DEG);
        RouteResult r = solver.solve(g, 0, cs.period(), SolverOptions.defaults());
        if (!r.hasRoute()) throw new AssertionError(cs.name() + ": solver returned no route");
        if (!ScheduleEvaluator.evaluate(g, r.schedule().route(), 0, cs.period()).feasible())
            throw new AssertionError(cs.name() + ": solver returned an infeasible route");
        List<Long> ids = new ArrayList<>();
        for (int v : r.schedule().route()) ids.add(g.destination(v).geoNameId());
        return new Outcome(r.visitedCount(), r.schedule().distanceKm(), ids);
    }

    static boolean matches(Exp e, Outcome o) {
        return e.visits() == o.visits() && Math.abs(e.deg() * KM_PER_DEG - o.km()) < 1e-6;
    }

    public static void main(String[] args) throws Exception {
        String emit = null;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--emit") && i + 1 < args.length) emit = args[++i];
            else throw new IllegalArgumentException("Usage: BoundaryCases [--emit file.json]");
        }
        RouteSolver[] solvers = { new NearestNeighbourSolver(), new GreedyInsertionSolver(), new BranchAndBoundSolver() };
        String[] names = { "nearest", "greedy", "exact" };
        List<Case> cases = cases();
        StringBuilder json = new StringBuilder("[");
        int failures = 0;
        System.out.printf("%-34s %-14s %-14s %-14s %s%n", "case (visits/degrees)", "nearest", "greedy", "exact", "suboptimal");
        for (Case cs : cases) {
            Exp[] exp = { cs.nearest(), cs.greedy(), cs.exact() };
            Outcome[] act = new Outcome[3];
            StringBuilder cells = new StringBuilder(), weak = new StringBuilder();
            for (int i = 0; i < 3; i++) {
                act[i] = run(solvers[i], cs);
                boolean ok = matches(exp[i], act[i]);
                if (!ok) failures++;
                cells.append(String.format("%-14s ", act[i].visits() + "/" + String.format("%.1f", act[i].km() / KM_PER_DEG) + (ok ? "" : "!")));
                if (act[i].visits() < exp[2].visits()
                        || (act[i].visits() == exp[2].visits() && act[i].km() > exp[2].deg() * KM_PER_DEG + 1e-6))
                    weak.append(weak.length() == 0 ? "" : ",").append(names[i]);
                if (!ok) System.out.println("  MISMATCH " + cs.name() + " " + names[i] + ": expected " + exp[i]
                        + " actual visits=" + act[i].visits() + " km=" + act[i].km() + " route=" + act[i].route());
            }
            System.out.printf("%-34s %s%s%n", cs.name(), cells, weak.length() == 0 ? "-" : weak);
            if (json.length() > 1) json.append(",\n");
            json.append("{\"name\":").append(q(cs.name())).append(",\"description\":").append(q(cs.description()))
                .append(",\"expected\":{");
            for (int i = 0; i < 3; i++)
                json.append(i > 0 ? "," : "").append(q(names[i])).append(":{\"visits\":").append(exp[i].visits())
                    .append(",\"distanceKm\":").append(exp[i].deg() * KM_PER_DEG).append("}");
            json.append("},\"actual\":{");
            for (int i = 0; i < 3; i++)
                json.append(i > 0 ? "," : "").append(q(names[i])).append(":{\"visits\":").append(act[i].visits())
                    .append(",\"distanceKm\":").append(act[i].km()).append(",\"route\":").append(act[i].route()).append("}");
            json.append("}}");
        }
        json.append("]\n");
        if (emit != null) Files.writeString(Path.of(emit), json.toString(), StandardCharsets.UTF_8);
        if (failures > 0) { System.out.println("FAIL: " + failures + " expectation mismatches"); System.exit(1); }
        System.out.println("PASS: " + cases.size() + " boundary cases x 3 algorithms match their hand-derived expectations.");
    }

    private static String q(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char ch : s.toCharArray()) {
            if (ch == '"' || ch == '\\') b.append('\\').append(ch);
            else if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch));
            else b.append(ch);
        }
        return b.append('"').toString();
    }
}
