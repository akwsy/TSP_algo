# Runnable application

Objective: maximize visited customers, then minimize distance among equal-count
routes. Customers can be skipped. Start at the first scenario destination, respect
customer time windows, and return within the time period. Waiting counts toward
the period; time spent at each destination is zero.

This folder runs independently of `evaluation/` and requires JDK 17 or newer.
Configure `JAVA_HOME` or make `java` and `javac` available on PATH.

From the repository root:

```sh
./submission/run.sh --start-time 08:00 --duration-minutes 120
./submission/run.sh --algorithm greedy --duration-minutes 60
./submission/run.sh --algorithm exact --time-limit-ms 10000 --max-destinations 15
./submission/run.sh --help
```

For manual compilation, enter this folder first:

```sh
javac --release 17 -d out src/graph/*.java src/algorithms/*.java src/app/*.java
java -cp out app.Main --start-time 08:00 --duration-minutes 120
```

The scripts resolve files relative to this folder. With the manual commands, use
this folder as the working directory. Alternative data paths supplied to the
scripts are therefore relative to this folder, or can be absolute paths supplied
by the caller. No particular installation or home directory is assumed.

## Inputs

`data/destinations.txt`: selected 19-column GeoNames rows, UTF-8 and tab-separated.
`data/windows.tsv`: IDs and inclusive `[opensAt, closesAt]` windows, in decimal
minutes after `startClock`. The first data row chooses the depot. Other rows are
potential customers, not mandatory visits and not a prescribed visiting order.

`data/scenario.properties`:

```properties
speedKmh=40
startClock=08:00
durationMinutes=120
```

`startClock` is the window/display origin and default departure clock.
`--start-time HH:mm` overrides departure without shifting windows. Alternatively,
`--start-time 60` means an offset of 60 minutes from the origin. A clock before the
origin is rejected; use a next-day minute offset such as 1440 for next-day starts.
`--duration-minutes` overrides the trip period. The budget includes waiting and
the return journey. It is unrelated to the solver's computation timeout.

Other options: `--algorithm both|greedy|exact` (`all` is an alias for `both`), `--speed`, `--data`,
`--time-limit-ms`, and `--max-destinations`. The size cap applies only to exact
search and includes the depot. Defaults: both submission algorithms, 40 km/h, 10,000 ms,
15 vertices including the depot; configuration can override speed and trip period.

To change candidates, edit the window rows and include the corresponding original
GeoNames rows in `destinations.txt`. Each ID must have one complete window.
Changing speed, time origin or departure can change feasibility.

Regenerate a variable selection **over the original `data/` files**. The full
GeoNames `MY.txt` and header-added spreadsheet are bundled in `inputs/`.
The Java generator reads `inputs/MY.txt`; the spreadsheet is for inspection.
From the repository root:

```sh
./submission/run.sh --generate inputs/MY.txt --count 25
./submission/run.sh --generate inputs/MY.txt --count 30 --selection random --seed 7
./submission/run.sh --generate inputs/MY.txt --count 50 --admin1 all --selection random --seed 42
./submission/run.sh --algorithm greedy --duration-minutes 180
```

`--count` includes the depot. Default customer filters are feature class `P` and
admin1 `14`; `--feature-class all` / `--admin1 all` remove a filter. `--depot` sets
the depot ID; it bypasses the customer filters. `--selection population` ranks by
population, while `random` samples without replacement using `--seed`.

Generation replaces `destinations.txt`, `windows.tsv`, `scenario.properties`,
`reference-tour.txt` and `DATA_NOTES.md` in `data/`, including existing manually
edited windows and settings. The source MY.txt is not changed. It must not be one
of those five output files. Invalid requests leave the current scenario unchanged.
No separate expanded data directory is needed.

Generation also accepts `--speed`, `--start-clock`, `--duration-minutes` and
`--window-slack-minutes`. Unspecified generation settings reset to defaults:
40 km/h, 08:00, 120 minutes and +/-30-minute window slack. The same source/options/
seed reproduce the selection and windows. The reference witness demonstrates
window feasibility with sufficient time, not feasibility within the trip budget.

Exact search still caps candidate sets at 15 vertices including depot by default;
use greedy for larger scenarios. The correctness suite creates its own temporary
fixtures, so regenerating `data/` does not require rewriting tests. See
`../PROJECT_GUIDE.md` for the full generation option table and examples.

## Outputs

Each solver prints its outcome, number visited, skipped customers, ordered visits,
arrival/wait/visit times, total distance, travel and waiting time, return clock,
runtime and work count. `OPTIMAL` means maximum visits and the shortest distance
for that count were proved by completed exact search. `FEASIBLE_HEURISTIC` gives
no proof. `SEARCH_LIMIT_REACHED` retains the current best feasible route without
claiming optimality. Zero visits is a valid answer, including when every customer
is unreachable. The depot never counts as a customer.

The application always returns to the depot by `departure + duration`. The depot's
own stored window constrains departure only. Invalid inputs produce a nonzero
process exit code; normal solver outcomes exit successfully. Output is printed
to the terminal; no result file is created automatically.

Distances are geographic Haversine estimates; constant-speed travel and windows
are simulated, not road/traffic or actual appointment data. See
`data/DATA_NOTES.md` for provenance and `../PROJECT_GUIDE.md` for the full project
guide. The source and input contract above are sufficient to run this folder alone.

## Evaluation tools are separate

The nearest-neighbour baseline and the HTML comparison UI/server live exclusively
in `../evaluation/`. This submission builds and runs on its own with greedy
insertion and branch and bound. It does not import or compile evaluation classes.

From the repository root, run `./evaluation/ui.sh` for the UI or
`./evaluation/compare.sh --algorithm nearest` for the baseline. Those tools reuse
this folder's graph, inputs, scheduler and submitted algorithms. See
`../evaluation/UI.md` for the UI instructions.
