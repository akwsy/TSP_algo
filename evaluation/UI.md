# Simple algorithm output viewer

## Start

From the repository root, with JDK 17+ configured:

```sh
./evaluation/ui.sh
```

Open `http://127.0.0.1:8765`. Use `--port 9000` for a different port, or
`--data data` for a scenario directory relative to `submission/`. Stop with Ctrl+C.
The HTML is in `evaluation/web/index.html`, but must be opened through the Java
server to run comparisons. There are no external libraries, map tiles or fonts.

## Read the output

1. Enter a departure offset (minutes from the saved window origin), trip period
   and simulated travel speed. The departure clock is displayed beneath the input.
2. Click **Compare algorithms**. All three run on identical Java graph/window data.
3. Read the visited count, distance, waiting, return clock and computation time.
4. Expand an algorithm's row for its route order, per-leg distances/travel, arrival,
   visit and waiting times, skipped locations and candidate/search-state counts.
5. Select a graph overlay, or use **Show on graph** inside a route's details.
   A single route overlay also numbers its visited stops.
6. Select an algorithm overlay, then click a destination. Its **physical arrival**
   on that route becomes the inspection clock, before any waiting. For example,
   Bukit Bintang is 08:04 on the default nearest-neighbour route, not 09:13.
   When showing all overlays, nearest neighbour supplies the clock. A location
   absent from the selected route is reached by adding direct travel from the
   previous clicked location; with no route selected, clicks form a manual walk.
7. Hover over another destination or a route segment. Details contain only the
   locations, distance, time taken, departure, arrival, location window and
   open/closed status. Wall clocks and travel durations use HH:mm; seconds are
   omitted without rounding calculation inputs. Click another location or use
   **Clear origin** to start again. Green means open, red means closed, and a blue
   outline marks the selected location. Colours are evaluated at the selected
   location's arrival time; a tooltip's status is evaluated at its target arrival.
8. Use **Export JSON** to download the current inputs and all solver results.

The view is deliberately plain: standard controls, readable tables and a basic
coordinate graph. Results come before the graph. Input data and dataset selection
are collapsed by default. Changing inputs clears stale results until compared again.

## Input edits and dataset replacement

Expand **Input data and dataset selection** to edit customer windows in minutes
from the displayed origin. These edits apply only to a comparison. Reload restores
the files. Departure and period are still constrained to valid nonnegative values.

The dataset form reads bundled `submission/inputs/MY.txt` and replaces the saved
`submission/data/` scenario, just like CLI generation. It exposes count, region,
feature class, depot, selection method, seed, slack and clock origin. Count includes
the depot. The current speed and period inputs are saved during generation.
A generated scenario must be compared again. Original full MY.txt is never modified.

The UI supports up to 200 vertices. Complete-graph connections can be toggled up
to 50 vertices; larger inputs show locations/routes without the dense edge layer.
This rendering choice does not change the complete graph used by Java.

## Algorithms and honest comparison

- **Nearest neighbour:** baseline; append the nearest feasible customer, reserve
  time to return, and break distance ties by GeoNameID. No reordering or proof.
- **Greedy insertion:** redesigned heuristic; insert feasible customers where added
  distance is smallest. No proof of maximum visit count.
- **Branch and bound:** exact reference; maximizes count, then minimizes distance,
  if search finishes. A time/size limit retains a feasible route without a proof.

The UI defaults to 1000 ms of computation per algorithm, exact cap 15 including
one depot. Advanced search controls allow 0–10000 ms and cap 1–20. These are
independent of the trip period. Computation checks are cooperative. Candidate
checks and exact states represent different work; runtime varies with warm-up and
machine load. Baseline quality is not guaranteed to rank below the other heuristic
on every input. Distance is only the secondary objective.

## Local API and files

The loopback server exposes only the static UI assets and these endpoints:

| Endpoint | Input | Output / effect |
|---|---|---|
| `GET /api/scenario` | None. | Saved destinations, coordinates, windows, speed, origin, period and graph counts. |
| `POST /api/compare` | URL-encoded `startTime`, `durationMinutes`, `speedKmh`, `timeLimitMs`, `maxDestinations`; optional complete `windows.tsv` text under `windows`. | Input snapshot and results of all three actual Java solvers; no files changed. |
| `POST /api/generate` | URL-encoded count, featureClass, admin1, depot, selection, seed, speedKmh, startClock, durationMinutes, windowSlackMinutes. | Replaces the saved scenario from bundled MY.txt; returns its input snapshot. |

Comparison JSON contains `scenario`, `startTime`, `durationMinutes`, `deadline`,
search options and `results`. Each result has algorithm ID/name, baseline flag,
status/message, count/runtime/work, route indices, per-visit schedule and leg
metrics, skipped indices, and distance/travel/waiting/finish totals. Route indices
refer to the same returned scenario; zero is the depot. `OPTIMAL` is reserved for
completed exact search. A capped exact search may return the feasible zero-visit
route; it is labelled as limited rather than as an optimal answer.

`src/evaluation/app/UiServer.java` handles local requests and static assets. `ComparisonService.java`
builds the shared solver result contract. `Json.java` writes JSON without packages.
`web/app.js` renders returned results; it does not implement routing algorithms.
`web/styles.css` provides basic formatting. No GitHub hosting is created: a static
GitHub Pages upload alone cannot execute the Java backend.

## Verification

`./evaluation/test.sh` runs algorithm tests and an ephemeral-server API suite.
The API tests cover three-solver output, capped searches, edited-window feasibility,
non-persistence of comparison edits, source-preserving dataset replacement,
invalid inputs and serving only intended assets. Browser checks cover readable
results, a different trip period, expandable routes and graph selection.

## Evaluation-only placement

All UI files, the server, comparison/JSON support and the nearest-neighbour
baseline belong to `evaluation/`. `build.sh` compiles the shared submission first,
then evaluation sources into `evaluation/out/`. The classpath contains both outputs;
there are no duplicate greedy or exact algorithm implementations. `ui.sh` runs
with `submission/` as the working directory so existing data/source paths keep
their meaning. It supplies the evaluation web-assets directory explicitly.

The submission has no evaluation imports. `../submission/run.sh` runs only greedy
insertion and branch and bound. `./compare.sh --algorithm nearest` runs the
evaluation baseline, while `./compare.sh` runs all three algorithms.

## Inspection clocks and windows

Clicking a scheduled destination uses the selected algorithm's `arrival`, not
`visitTime` after waiting. This is a display/inspection feature; Java solvers keep
their original feasibility and waiting rules. The selected route determines the
clock; all-overlays mode uses nearest neighbour. After changing overlays, the
selected stop's arrival is recalculated. After input edits, stale results are
removed and inspection returns to the departure clock until compared again.

Destination hovers estimate direct travel leaving the selected stop at its
inspection clock, without adding a new wait. Their departure is that clock and
their arrival is departure plus travel. Route-segment hovers use the solver's
actual leg departure and arrival; departure can be later than the previous stop's
arrival when the solver waited for it to open. The route table explicitly shows
both departure and physical arrival, plus status at arrival, avoiding confusing
arrival with service time.

Distance comes from the Java graph's `distanceKm` matrix. Destination/edge travel
time is distance times 60 divided by current speed; route travel comes from the
solver's saved leg. These are one-way inspections, not a new optimal route.

Open means the inspection/arrival falls inside the inclusive window; closed
means before opening or after closing. Invalid windows are grey/unknown. The
depot is always available for inspection. Computation retains full precision;
HH:mm display drops seconds, so boundary status may be more precise than the
visible clock. Durations also display HH:mm. Next-day clocks retain a day suffix.

The selected location resets on reload/dataset replacement. Keyboard focus shows
hover details, Enter/Space selects a location, and Escape hides the tooltip.

Optional UI-only helper checks with Node.js (not required to run Java or the UI):

```sh
node evaluation/tests/inspection.test.cjs
```

The 19 checks cover the Bukit Bintang physical arrival, cumulative travel,
minute-only formatting and inclusive opening/closing boundaries.
