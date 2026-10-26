# Evaluation

The nearest-neighbour baseline, plain HTML UI/server, comparison runner and tests
are evaluation-only tools. They exercise the current algorithm source in `../submission/`. They are
not needed to run the submission folder on its own. Require a configured JDK 17+.

From the repository root:

```sh
./evaluation/test.sh
./evaluation/compare.sh --start-time 08:00 --duration-minutes 120
./evaluation/compare.sh --start-time 08:00 --duration-minutes 60
```

`build.sh` compiles application classes to `submission/out/` and evaluation
classes to `evaluation/out/`. `test.sh` also compiles tests to `evaluation/out/`
and runs with `submission/` as its working directory.
`compare.sh` runs all three algorithms on identical supplied inputs. Options such
as `--data` are forwarded to the application. Relative data paths resolve inside
`submission/`.

## Launch the UI or baseline

```sh
./evaluation/ui.sh
./evaluation/compare.sh --algorithm nearest --duration-minutes 120
```

Open `http://127.0.0.1:8765` for the plain comparison view. See [UI.md](UI.md).
The nearest-neighbour implementation is `src/evaluation/algorithms/NearestNeighbourSolver.java`.
UI/server/comparison support is in `src/evaluation/app/`; HTML/CSS/JS is in `web/`.
Both runners reuse the actual graph, scheduler, greedy and exact algorithms in
`submission/`. The submission does not depend on or compile these evaluation files.

## Files

- `tests/TestSuite.java`: validation, scheduling and objective tests; an independent
  oracle enumerates all ordered subsets, including the empty subset, for 100
  seeded cases with 2–7 vertices. It compares visit count and distance tiebreak.
  Returned routes are independently checked for uniqueness, windows, waiting,
  distance, zero service duration and return within the period.
- The current witness lives in `../submission/data/reference-tour.txt` alongside
  the regenerated scenario. The tests independently generate their own witnesses
  in temporary directories; solvers never read any witness.
- `tests/UiServerTest.java`: starts an ephemeral loopback server and tests actual
  Java results, edited windows, regeneration, escaping, validation and static assets.
- `build.sh`: builds submission, then evaluation sources.
- `ui.sh`: starts the evaluation-only local viewer; `UI.md` documents its controls.
- `src/evaluation/app/ComparisonMain.java`: evaluation CLI and baseline selection.
- `test.sh`: compiles and executes both suites; exits nonzero on a failed assertion.
- `compare.sh`: prints all three solver results on a selected scenario.
- `.gitignore`: excludes generated output and system metadata.

Focused cases cover exact closing and return deadlines, a budget consumed by
waiting, forbidden lateness, skipping, duplicate visits, zero periods, zero-travel
visits, nonzero start offsets, maximum count before minimum distance, a heuristic
that misses achievable visits, timeout/cap results retaining a feasible route,
input errors, deterministic generation, in-place replacement, variable counts, filters, seeds and source preservation and CLI clock inputs.

Latest verification: **7,604 algorithm assertions and 37 UI/API assertions passed**, including 100 independent
subset-oracle cases. Nearest neighbour is independently checked for feasibility and against the
maximum-count oracle, alongside greedy and exact search. API tests use disposable
source/scenario data; no current scenario is replaced by tests. Loopback network
access is needed for the UI/API tests.

## Demonstration results

Start 08:00, default 40 km/h, simulated windows, zero service duration:

| Period | Solver | Customers visited | Distance | Return clock |
|---|---|---:|---:|---|
| 120 min | Nearest neighbour baseline | 5 / 9 | 29.793326 km | 09:53:58 |
| 120 min | Greedy insertion | 8 / 9 | 56.003768 km | 09:49:58 |
| 120 min | Branch and bound | 9 / 9 (proved optimal) | 65.351488 km | 09:50:23 |
| 60 min | Nearest neighbour baseline | 2 / 9 | 11.477287 km | 08:51:25 |
| 60 min | Greedy insertion | 4 / 9 | 28.646396 km | 08:54:33 |
| 60 min | Branch and bound | 4 / 9 (proved optimal) | 27.050187 km | 08:51:25 |

The greater distance of the 120-minute exact answer is acceptable: it visits one
more customer, which is the primary objective. Runtime varies by environment.
These are small demonstration results, not a formal benchmark study.

The correctness suite uses synthetic temporary GeoNames/scenario fixtures, not the
current `submission/data/`, so it works after that scenario has been regenerated
with another size, region, seed or depot. The table above records the default
10-vertex selection; comparison output changes after regeneration.

Regenerate the original scenario with `./submission/run.sh --generate` and compare
it with `./evaluation/compare.sh`. If presentation results rely on these tools,
include the relevant tools, generation settings and inputs with the submission.

## Browser checks

Launch `./evaluation/ui.sh` and verify the three output rows, expandable route
tables and graph overlays. Changing the period from 120 to 60 on the default
scenario should produce 2/4/4 visits for nearest/greedy/exact. Input changes clear
stale results; comparison-only window edits do not rewrite saved data. The dataset
form explicitly replaces the saved scenario. The page requires no external assets.

Hover inspection: click a graph point to choose the measurement origin, then
hover another point or a route segment for distance and travel time. This does
not change the routing depot. Matrix values are checked against the Java graph.
See UI.md for keyboard controls and travel-versus-waiting interpretation.

Inspection now shows HH:mm clocks, physical arrival before waiting, and green/red
open/closed colours at the selected stop's arrival. Hover details are limited to
distance, time taken, departure, arrival, window and status. Optional display-helper
checks: `node evaluation/tests/inspection.test.cjs` (19 checks).
