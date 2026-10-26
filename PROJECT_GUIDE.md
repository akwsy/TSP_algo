# Project guide: maximize destination visits within a time period

## 1. Current project requirements

Given a set of potential destinations, a starting depot, a departure time and an
available period, find a feasible round trip that **maximizes the number of
customer destinations visited**. Among routes with the same visit count, prefer
the one with the shortest total distance. The depot is excluded from the count.

This changes the original all-destinations-required, minimum-distance TSP into a
maximum-visit routing problem with time windows and a time budget.

The current implementation contract is:

1. Depart from the selected depot at a fixed starting time.
2. Customers are optional. Visit any chosen customer at most once.
3. Respect each visited customer's inclusive opening/closing window. Early
   physical arrival may wait until opening; late visits are forbidden.
4. Spend zero service time at each customer.
5. Return to the same depot no later than `departure + period`.
6. Include travel, waiting and the return journey in the period.
7. Maximize distinct customer visits first; minimize distance second.
8. Provide nearest neighbour as a baseline, greedy insertion as a redesigned
   heuristic and branch and bound as an exact reference, sharing graph,
   scheduling rules, objective and scenario inputs.
9. Report the route and skipped customers transparently; never call a limited
   search optimal unless the exact search has finished.
10. Keep application/submission files separate from evaluation tools and avoid
    workstation-specific paths or dependencies.

A zero-customer route `[depot, depot]` is valid. If all customers are unreachable,
the exact optimum is zero visits rather than an infeasible instance. A zero-minute
period is allowed; only zero-travel visits whose windows contain the departure
can then fit. The depot's stored window restricts departure, while the trip
period restricts return. No additional depot closing-time rule is applied.

**Defaults chosen for the demonstration:** departure 08:00, period 120 minutes,
constant speed 40 km/h, ten vertices including the depot. All are documented
inputs rather than real road/appointment measurements.



## 2. Inputs

### Geographic records: `submission/data/destinations.txt`

UTF-8, tab-separated, with the original 19 GeoNames fields and no header. Empty
columns must be preserved. Routing uses GeoNameID, name, latitude and longitude.
The default selection additionally uses feature class, administrative code and
population. Names are display labels; GeoNameIDs identify destinations uniquely.

Only selected destinations get graph vertices. The supplied demonstration has
nine potential customer destinations plus Kuala Lumpur as the depot. The full
source dataset is not needed to run the demonstration.

### Windows and candidate selection: `submission/data/windows.tsv`

Three tab-separated columns, with this exact header:

```text
geonameid	opensAt	closesAt
```

Each following row provides a GeoNameID and inclusive numeric window. The first
row selects the depot; the others select potential customers. Row order does not
prescribe the route. Every selected ID must exist in `destinations.txt`. Extra
geographic records can be present without becoming candidate visits.

Windows are decimal minutes relative to `startClock`. For an 08:00 origin,
`[60, 90]` means 09:00–09:30. A customer may be skipped. Duplicate IDs, missing
values, invalid coordinates and reversed windows are rejected. Window values
must be finite, nonnegative and ordered. Full precision is kept internally;
a 1e-9-minute tolerance handles numerical boundary noise.

### Scenario properties: `submission/data/scenario.properties`

| Property | Default | Meaning |
|---|---|---|
| `speedKmh` | `40` | Positive constant speed for simulated travel times. |
| `startClock` | `08:00` | Window/display origin and default departure clock. |
| `durationMinutes` | `120` | Available trip period, including waiting and return. |

Changing `startClock` shifts the absolute interpretation of all windows. To change
only departure while keeping appointments fixed, use `--start-time`.

### Command-line overrides

Run from the repository root, using a configured JDK 17 or newer:

```sh
./submission/run.sh --start-time 08:30 --duration-minutes 90
./submission/run.sh --algorithm exact --time-limit-ms 10000 --max-destinations 15
./submission/run.sh --algorithm greedy --speed 30
```

| Option | Meaning |
|---|---|
| `--start-time HH:mm` | Departure on the origin day; must not precede `startClock`. |
| `--start-time number` | Alternative decimal-minute departure offset from `startClock`; next-day offsets are supported. |
| `--duration-minutes number` | Nonnegative finite trip period; overrides the property. |
| `--speed number` | Positive finite simulated speed; overrides the property. |
| `--data directory` | Scenario directory; scripts resolve relative paths within `submission/`. |
| `--algorithm both\|greedy\|exact` | Submission algorithms; default both. `all` is an alias for both. The evaluation runner additionally supports `nearest`. |
| `--time-limit-ms integer` | Computation budget per solver, default 10000. This is separate from trip duration. |
| `--max-destinations integer` | Exact-search cap including depot, default 15. |
| `--help` | Print supported options. |
| `--generate source [selection options]` | Replace the scenario in `submission/data/` using a variable selection from GeoNames. |

The start and period must yield a finite deadline. Invalid inputs exit with a
nonzero process code. Solver timeouts and normal answers exit successfully and
are distinguished by their reported status.

### Generate a variable destination selection from MY.txt

The original full `MY.txt` is now bundled at `submission/inputs/MY.txt`; there is
no download or manual copy step. The header-added Excel workbook is included
beside it for inspection. Original course/data documentation is in `docs/`.
The scripts resolve relative source paths from `submission/`. From the repository root:

```sh
# Replace the ORIGINAL scenario with 25 vertices: one depot and 24 customers.
./submission/run.sh --generate inputs/MY.txt --count 25

# Replace it with a reproducible random set of 30 vertices from the same region.
./submission/run.sh --generate inputs/MY.txt --count 30 --selection random --seed 7

# Select across all administrative regions, keeping populated places only.
./submission/run.sh --generate inputs/MY.txt --count 50 --admin1 all --selection random --seed 42

# Choose a different region and depot (the depot ID must exist in MY.txt).
./submission/run.sh --generate inputs/MY.txt --count 20 --admin1 02 --depot 1222382

# Solve the newly replaced scenario; use greedy for a larger candidate set.
./submission/run.sh --algorithm greedy --start-time 08:00 --duration-minutes 180
```

There is no need to create `data-expanded/`, copy selected rows manually, or edit
Java code. `--count` includes the depot, which is never counted as a visited
customer. Generation writes the current scenario to `submission/data/` every time.

**What is replaced:** `destinations.txt`, `windows.tsv`, `scenario.properties`,
`reference-tour.txt` and `DATA_NOTES.md`. Existing manual windows/settings in those
files are replaced, not merged. The original full `MY.txt` is read only and must
not be one of those output files. Other files in `data/` are left alone.

| Generation option | Default | Meaning |
|---|---|---|
| `--count` | `10` | Total number of selected vertices, including one depot. |
| `--feature-class` | `P` | Filter customers by feature class; `all` disables this filter. |
| `--admin1` | `14` | Filter customers by administrative code; `all` disables this filter. Preserve leading zeroes, such as `02`. |
| `--depot` | `1735161` | Explicit depot GeoNameID, included even if outside the customer filters. |
| `--selection` | `population` | `population` selects highest population first (ID breaks ties); `random` samples without replacement by seeded shuffle. |
| `--seed` | `42` | Controls random customer selection and the shuffled reference route used for windows. |
| `--speed` | `40` | Simulated travel speed used in generated properties and windows. |
| `--start-clock` | `08:00` | Generated window origin and default departure clock. |
| `--duration-minutes` | `120` | Default trip period saved in the replaced configuration. |
| `--window-slack-minutes` | `30` | Window half-width around simulated reference arrival, with openings clipped to zero. |

For example, add `--duration-minutes 180` during generation to save that default,
not merely override it for one solve. Unspecified settings reset to the generation
defaults above rather than inheriting previous manual changes.

The depot is removed from the customer candidate pool before selection, then
placed first in the output. Population selection is deterministic. Random
selection starts with ID-sorted eligible records, then shuffles using the seed;
the same source/settings/seed reproduce the selected IDs and windows. Change the
seed for another reproducible sample. Generated selection parameters are recorded
in `scenario.properties` and `DATA_NOTES.md`, without storing the source device's
path. There is no automatic geographic-radius constraint, so selecting across
Malaysia may yield long trips and few visits within a short period.

Every selected customer receives an automatically generated simulated time window.
The reference tour establishes that the windows are mutually feasible with enough
time, but is not guaranteed to fit the configured period. Choosing a smaller
period means the solvers may skip customers, as intended.

Generation validates the source, count, filters and depot before replacement. A
request exceeding the available eligible records fails and leaves the previous
scenario unchanged. Files are staged before replacement; normal replacement I/O
failures trigger restoration of already replaced files. This is not a multi-file
transaction against a process/power interruption; avoid concurrent generators.

The loader can read the full source without constructing its full graph. Window
generation computes only reference-route legs; solving subsequently builds the
O(n²) graph for the selected records. Exact search still defaults to a 15-vertex
cap including depot and can time out even below that cap. Greedy also becomes
slower as count grows; use larger candidate sets thoughtfully.

Correctness tests use synthetic fixtures rather than the mutable current scenario,
so changing the number or selection in `submission/data/` does not invalidate the
baseline test suite. Compare the current scenario with `./evaluation/compare.sh`.

### Java interface

```java
RouteResult solve(DestinationGraph graph,
                  double startTime,
                  double timePeriod,
                  SolverOptions options)
```

The graph contains coordinates, windows, distances and travel minutes; vertex
zero is the depot. Start and period are decimal minutes on the scenario timeline.
`SolverOptions` controls computation only. The earlier three-argument interface
has been replaced so the trip period is explicit.

## 3. Graph, scheduling and algorithms

The graph is complete, undirected, weighted and static. Two symmetric adjacency
matrices store distance and travel time. Each vertex stores its destination
window. Graph construction and storage cost O(n²) for the selected vertices.

Distance is Haversine distance using Earth radius 6371.0088 km:

```text
travelMinutes(i, j) = distanceKm(i, j) * 60 / speedKmh
arrival(j) = previous departure + travelMinutes(i, j)
visit(j) = max(arrival(j), opening(j))
departure(j) = visit(j)              # zero service duration
return deadline = startTime + timePeriod
```

Customer visit time must not exceed closing time. Every candidate answer includes
the return leg and must finish within the deadline. Waiting consumes the same
budget as travelling. Rounding is for displayed output only.

**Nearest neighbour baseline:** append the closest feasible unvisited customer
from the current location, respecting its window and reserving travel time for
return to the depot. Equal-distance ties use GeoNameID. Early arrival may wait;
selection is by distance, not earliest window. Do not reorder previous visits.
Stop when no feasible next customer remains or the computation budget expires,
retaining the feasible route. This is a constraint-aware baseline for this
variant, rather than classic nearest neighbour that ignores windows and period.
Its worst-case time is O(n²), with O(n²) total storage including the graph. It may
lose visits by waiting at a nearby customer while other customers' windows close.

**Greedy insertion:** start with depot → depot. Evaluate every unvisited customer
at every insertion position and reschedule the whole route, including the return.
Among feasible insertions choose the smallest added distance; ties use closing
time, GeoNameID and insertion position. Continue adding visits until none fits or
the computation budget expires. Every committed insertion adds one customer.
The final subset is feasible but need not have maximum cardinality; no swaps or
removals are attempted to recover from poor earlier choices. Straightforward
rescheduling gives O(n⁴) worst-case time and O(n²) storage including the graph.

**Branch and bound:** explore customer subsets and orders by depth-first search.
Every route prefix closed at the depot is a candidate answer, not only a route
that visits everybody. Seed the incumbent with greedy's feasible subset. A node's
count upper bound is the number already visited plus the number of individually
reachable unvisited customers. Individual reachability checks both the customer's
window and its optimistic direct return within the budget. Exclude an unreachable
customer, rather than rejecting the entire node. Prune when that optimistic count
cannot beat the incumbent. When only a count tie is possible, the travelled
distance plus direct return provides a safe lower bound for distance pruning.
This replaces the old all-customers MST bound, which would not be valid for the
new optional-visit objective.

These bounds depend on the triangle inequality and constant-speed metric travel.
Exact search is factorial in the worst case, with polynomial work per node; the
15-vertex cap is not a runtime guarantee. The greedy incumbent pass shares its
10-second computation budget. A limited search retains the best known feasible
subset, including the depot-only route if no visit has been found. Time checks
are cooperative between operations, not hard process termination deadlines.

## 4. Outputs

All three solvers report:

- Outcome and whether optimality is established.
- Customer visit count, excluding the depot, against the number of candidates.
- Skipped customer IDs and names.
- Ordered route, including departure and return to the depot.
- Physical arrival, visit time after waiting, waiting and customer windows.
- Distance, travel minutes, total waiting, finish time and return clock.
- Computation runtime and explored candidates/states.

`RouteResult` holds the status, schedule, runtime, work count and message, and
exposes `visitedCount()`. `Schedule` holds route indices, visit records and totals.
The application maps route indices back to names/GeoNameIDs for display. The clock
column is visit time after waiting. Results are printed; no output file is saved
automatically. Heuristic candidate counts and exact state counts measure different
work and should not be compared as equal units.

| Status | Interpretation |
|---|---|
| `FEASIBLE_HEURISTIC` | A valid subset from nearest neighbour or greedy insertion; no optimality proof. |
| `OPTIMAL` | Completed exact search proved maximum visits and minimum distance for that count. |
| `SEARCH_LIMIT_REACHED` | Computation timeout or exact-search cap; best known feasible subset, no proof. |

An impossible-to-reach customer does not make the whole instance infeasible.
Empty feasible routes and skipped destinations are normal outcomes. Earlier
`INFEASIBLE` and `HEURISTIC_DEAD_END` statuses were removed for this objective.

### Plain HTML viewer

Run `./evaluation/ui.sh` from the repository root and open
`http://127.0.0.1:8765`. This is an evaluation-only local output viewer backed by the actual Java
solvers, not a second JavaScript implementation of the algorithms. A running
Java server is required; opening the HTML file directly is not sufficient.

The page uses basic controls and tables: comparison results appear first, each
algorithm expands into its ordered route, and the geographic graph appears below.
Select a route overlay. Click a destination to use its physical arrival on the selected route as the
inspection clock (08:04 at Bukit Bintang on the baseline, before waiting). Hover
for distance, time taken, departure, arrival, window and open/closed status.
Clocks and durations use HH:mm. Destinations are green/open or red/closed at
the selected clock, with a blue outline for the selected location. This inspection does not change the routing depot. Hover values
use the Java graph distance matrix included in the scenario API. Input windows are editable for one comparison. Reload restores saved
inputs. The dataset form replaces the current saved scenario using the bundled
MY.txt. Results can be exported as JSON. See `evaluation/UI.md` for all controls and the
local API. No UI data is sent to an external service.

The UI limits selections to 200 vertices and hides full connection lines above
50 for readability. The exact solver still observes its own size/time limits.
The default UI computation budget is 1000 ms per algorithm, distinct from the
trip period and the CLI default of 10000 ms. A computation or size limit is shown
without claiming optimality. Runtime statistics are measurements, not benchmark
claims; warm-up and machine conditions affect them.

## 5. Every tracked project file

Generated classes, `out/` directories and OS metadata are not project sources.
The following inventory describes the files intended for version control.

| File | Purpose |
|---|---|
| `README.md` | Repository entry point, quick start and links. |
| `PROJECT_GUIDE.md` | This complete requirements/input/output/file guide. |
| `docs/Project_2627T1.pdf` | Unchanged original project brief; its additional instructions remain separate from the implementation contract. |
| `docs/Metadata.txt` | Original GeoNames schema, licence and metadata. |
| `docs/Read Me.txt` | Original dataset provenance and supporting references. |
| `docs/SOURCE_FILES.md` | Original-file inventory, byte sizes and SHA-256 integrity hashes. |
| `submission/inputs/MY.txt` | Full 71,709-record source dataset for generating variable selections. |
| `submission/inputs/MY-All-columns_with_header.xlsx` | Original header-added Excel dataset for manual inspection. |
| `.gitignore` | Ignore generated Java files and OS metadata throughout the repository. |
| `submission/README.md` | Standalone application run instructions and input format. |
| `submission/.gitignore` | Keep generated output and metadata out of a standalone submission checkout. |
| `submission/build.sh` | Compile application code with Java 17 compatibility to `submission/out/`. |
| `submission/run.sh` | Locate the project, build, then run the application with supplied arguments. |
| `submission/java-env.sh` | Locate Java through `JAVA_HOME` or PATH, without fixed installation paths. |
| `submission/src/graph/Destination.java` | Immutable destination ID/name/coordinates/window and validation. |
| `submission/src/graph/DestinationGraph.java` | Depot-first vertices, ID lookup, Haversine distances and travel-time matrices. |
| `submission/src/graph/GeoNamesLoader.java` | Validate/read 19-column GeoNames input and select the reproducible demo subset. |
| `submission/src/algorithms/RouteSolver.java` | Common graph/start/period/options solver interface. |
| `submission/src/algorithms/SolverOptions.java` | Computation timeout, exact-search size cap and monotonic elapsed-time check. |
| `submission/src/algorithms/RouteResult.java` | Outcome, schedule, visit count and solver statistics. |
| `submission/src/algorithms/ScheduleEvaluator.java` | Shared subset route validation and zero-service scheduling within the period. |
| `evaluation/src/evaluation/algorithms/NearestNeighbourSolver.java` | Constraint-aware nearest-neighbour baseline, appending feasible visits. |
| `submission/src/algorithms/GreedyInsertionSolver.java` | Feasible insertion heuristic for accumulating visits. |
| `submission/src/algorithms/BranchAndBoundSolver.java` | Exact maximum-visit subset/order search with distance tiebreak. |
| `submission/src/app/ScenarioFiles.java` | Load scenarios; stage and replace current scenario files with reproducible generated inputs. |
| `submission/src/app/GenerationOptions.java` | Validate generation selection, speed, clock, period and window-slack settings. |
| `evaluation/src/evaluation/app/ComparisonService.java` | Shared scenario/result contract, running all three real Java solvers and checking returned routes. |
| `evaluation/src/evaluation/app/Json.java` | Dependency-free JSON serializer for API results. |
| `evaluation/src/evaluation/app/UiServer.java` | Loopback HTTP server for the HTML viewer, scenario input, comparison and generation endpoints. |
| `evaluation/ui.sh` | Build shared submission code and evaluation tools, then launch the viewer. |
| `evaluation/build.sh` | Build submission classes first, then evaluation-only Java classes into separate output folders. |
| `evaluation/src/evaluation/app/ComparisonMain.java` | Evaluation CLI for nearest neighbour and the two shared submission solvers. |
| `evaluation/web/index.html` | Plain input controls, result disclosures, graph and dataset form. |
| `evaluation/web/styles.css` | Minimal readable layout, tables and route colors. |
| `evaluation/web/inspection.js` | Minute-only clock/duration formatting, physical route arrivals and inclusive window-status helpers. |
| `evaluation/tests/inspection.test.cjs` | Optional dependency-free Node checks for inspection clocks and window boundaries. |
| `evaluation/web/app.js` | Request Java results, draw the SVG graph, show statistics/route tables and export JSON. |
| `evaluation/UI.md` | HTML viewer launch commands, interaction guide, limits and API contract. |
| `evaluation/tests/UiServerTest.java` | Temporary-server integration tests for API results, edits, generation, validation and static assets. |
| `submission/src/app/Main.java` | Parse CLI inputs, run solvers, recheck schedules and print routes/results. |
| `submission/data/destinations.txt` | Ten selected, unchanged GeoNames geographic rows. |
| `submission/data/windows.tsv` | Editable candidate/depot IDs and simulated customer windows. |
| `submission/data/scenario.properties` | Simulated speed, clock origin and default trip period. |
| `submission/data/DATA_NOTES.md` | Geographic provenance, licence reference, selection and simulated-input methodology. |
| `evaluation/README.md` | Evaluation coverage, commands and current demonstration results. |
| `evaluation/.gitignore` | Exclude generated evaluation classes and metadata. |
| `evaluation/test.sh` | Build the current submission and run the independent test suite. |
| `evaluation/compare.sh` | Run all three algorithms on the same scenario and forward CLI options. |
| `evaluation/tests/TestSuite.java` | Focused regression tests, CLI checks and independent exhaustive subset oracle. |
| `submission/data/reference-tour.txt` | Current generated witness; used for generation evidence, not read by solvers and not guaranteed to fit the period. |

The nearest-neighbour baseline, UI assets, HTTP server, JSON/comparison layer and
comparison CLI live only in `evaluation/`. Their Java packages are
`evaluation.algorithms` and `evaluation.app`. They depend on shared submission
classes; submission classes have no dependency on evaluation.

The `submission/` folder runs without `evaluation/`. Evaluation uses the same
algorithm sources and baseline data, so fixes do not need to be duplicated.
Regenerate the original `submission/data/` for new selections. Tests construct
their own temporary source/scenario fixtures and do not assume the current demo
contains a fixed number of vertices.

## 6. Verification and collaboration

Run from the repository root:

```sh
./evaluation/test.sh
./evaluation/compare.sh --start-time 08:00 --duration-minutes 120
```

The suite checks maximum count and distance tiebreak against all ordered subsets
for 100 seeded tiny instances. It independently validates returned routes and
covers waiting, deadlines, skipped/unreachable customers, zero periods, zero-time
travel, invalid inputs, timeouts, size caps, variable in-place generation, customer filters, seeds, source preservation and command-line starts.
The recorded run passed **7,604 algorithm assertions and 37 UI/API assertions**. See `evaluation/README.md` for
observed demo results; runtimes vary by environment.

For GitHub collaboration, commit source, scripts, scenario data and documentation.
Do not commit generated `out/` directories or `.class` files. The scripts resolve
the checkout location dynamically. Teammates configure their own JDK through
`JAVA_HOME` or PATH. Changes to the objective, input contract or scenario data
should update the guide and tests in the same commit. The GitHub remote is `https://github.com/akwsy/TSP_algo.git`.
No software licence for the Java code has been assigned automatically.

The selected geographic data retains GeoNames provenance and the source's CC BY
4.0 reference in `DATA_NOTES.md`. The data licence statement does not establish a
licence for the Java code. All five original files are bundled unchanged in
`docs/` and `submission/inputs/`; external originals also remain unchanged.
See `docs/SOURCE_FILES.md` for the inventory and SHA-256 integrity hashes.
