# Black-box test brief: maximum-visit routing with time windows

You are an independent tester. You have NOT seen the implementation and must not look for it.
Do not read, list, decompile (javap etc.) or search any file outside this `sim/` directory
except to run `./runner.sh`. Tests must be derived only from this specification.

## Problem (the contract the 3 algorithms must satisfy)
Given a depot, optional customers, a departure time and a trip period, find a closed route
depot -> customers... -> depot.
1. Depart the depot at the start time (minutes; depot window restricts departure: start must lie in [depot.opensAt, depot.closesAt]).
2. Customers are optional; each is visited at most once. Depot appears only first and last.
3. Each visited customer has an inclusive window [opensAt, closesAt] (minutes). Arriving early means
   waiting until opensAt; arriving after closesAt is forbidden.
4. Service time is zero.
5. Return to the depot no later than start + period (inclusive; tolerance 1e-9 min). Waiting counts.
6. Objective: maximize number of distinct customers visited (depot excluded); ties -> minimize total distance (km).
7. Travel: great-circle (haversine) distance, Earth radius 6371.0088 km; travel minutes = km * 60 / speedKmh.
8. Route [depot, depot] (zero customers) is valid. Period 0 is allowed.
Three algorithms: `nearest` (greedy baseline heuristic), `greedy` (insertion heuristic), `exact` (branch and bound).
- exact must return the true optimum per (6) and status OPTIMAL when it completes within its limits.
- nearest and greedy must always return a FEASIBLE route (per 1-5), may be suboptimal, and must never
  beat exact on visit count (or on distance at equal count). Heuristic status: FEASIBLE_HEURISTIC.
- If a search limit is hit, status is SEARCH_LIMIT_REACHED and the route must still be feasible.

## Input files (a scenario directory)
- `destinations.txt`: UTF-8, TAB-separated, NO header, 19 GeoNames columns (empty columns preserved).
  Used columns (1-based): 1 geonameid, 2 name, 5 latitude, 6 longitude. Others may be anything plausible
  (col 7 feature class e.g. P, col 11 admin1 code e.g. 14, col 15 population). IDs unique, positive; names non-blank.
- `windows.tsv`: header exactly `geonameid<TAB>opensAt<TAB>closesAt`. FIRST data row = the depot; other rows = candidate customers.
  Values are decimal minutes relative to startClock, finite, >= 0, opensAt <= closesAt. Depot may use closesAt 1.7976931348623157E308.
  Every ID must exist in destinations.txt. Duplicate IDs / reversed windows / bad coords must be rejected (nonzero exit).
- `scenario.properties`: `speedKmh=40.0`, `startClock=08:00`, `durationMinutes=120.0` (plus optional selection* keys that can be ignored).

## How to run (the only access you have)
```
./runner.sh --algorithm nearest|greedy|exact|all --data /abs/scenario/dir \
   [--start-time HH:mm | minutes-offset] [--duration-minutes N] [--speed KMH] \
   [--time-limit-ms N] [--max-destinations N]    # max-destinations counts the depot, default 15
```
`--start-time HH:mm` must not precede startClock; a plain number is a minute offset from startClock (default 0).
Invalid input exits nonzero with `Error: ...` on stderr. Normal answers (including limit hits) exit 0.

Output per algorithm (parse these lines; ignore Runtime):
```
<Name>: <STATUS>
<message>
Visited: K/N customers
Distance: D km; travel: T min; waiting: W min; return: HH:MM:SS
Route: A -> B -> ... -> A          (names)
Skipped: names or none
  <id> <name>: arrival HH:MM:SS; visit HH:MM:SS; wait X min     (one line per stop, depot first and last)
```
Use unique city names in generated data so Route lines map back to IDs.

## What to build (in `sim/`, Python 3 stdlib only, no pip)
1. `gen.py`: seeded random scenario generator writing scenario dirs under `sim/scenarios/`.
2. `oracle.py`: an INDEPENDENT brute-force solver written from the spec above (enumerate all ordered subsets, n <= 8 customers),
   plus a `validate_route()` that independently checks any reported route/times against rules 1-8.
3. `run_sims.py`: runs many scenarios across all 3 algorithms and checks:
   - exact == oracle (visit count, then distance within 1e-6 km), status OPTIMAL
   - every route from every algorithm passes validate_route; reported Visited/Distance/return match your recomputation
   - nearest/greedy visits <= exact visits, and distance >= exact when equal
   - determinism: the same input twice yields the same route
   - Scenario families (at least ~15 each where sensible): random; zero period; period too small for anyone;
     all customers unreachable; window closing exactly at arrival; early arrival with waiting; depot-only window;
     1 customer; 8 customers with generous windows; tight deadlines; clustered/colinear/duplicate-coordinate points (ties);
     speed variations; start offsets (HH:mm and numeric incl. past 24h); `--max-destinations` below size (cap) -> still feasible route;
     `--time-limit-ms 0` -> feasible route, limit status allowed.
   - Invalid inputs exit nonzero: duplicate ID, reversed window, NaN/negative window, unknown ID in windows, bad latitude, negative duration, speed 0.
4. `REPORT.md`: counts of scenarios per family, pass/fail, every failure with the scenario dir and a minimal reproduction command,
   and anything in this spec that was ambiguous (list ambiguity separately from failures).
Do NOT adjust tests to make them pass; if behavior disagrees with the spec, report it. Keep scenarios small enough that the whole run takes a few minutes.
