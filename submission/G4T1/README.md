# Routing algorithm experiments (group 4, tutorial 1)

From a depot, a vehicle leaves at a given time and must return within a period, visiting as many distinct customers as possible, each within its one time window (four slots over 06:00 to 24:00). Ties go to the shorter distance. This folder holds three routing algorithms written by the team, a test harness that builds problems from a real dataset (GeoNames places in Malaysia), runs every algorithm on the same problems and checks every answer independently, the experiments we present (7 folders under `experiments/`), and a website to look at the results. It contains all the source code and data needed to reproduce the experiments; no saved results are included.

## Folder structure

```
G4T1/
  README.md                this file
  start.py                 run the default evaluation, then open the website
  run_all_experiments.py   run all experiments below, in order (--quick for a small run)
  experiments/             one folder per experiment (README.md + run.py; output/ appears when run)
    01-scaling-number-of-customers/   `scaling`: varies customers over 5, 10, 15, 20, 30, 50, 100
    02-time-budget-travel-period/   `time-budget`: varies period over 240, 480, 720, 960, 1080
    03-speed-travel-speed/   `speed`: varies speed over 20, 30, 40, 60, 80
    04-window-alignment-departure-time/   `window-alignment`: varies departure over 360, 540, 720, 900, 1080
    05-spread-customer-radius/   `spread`: varies radius over 25, 50, 100, 150, 250
    06-stress-large-problems/   `stress`: varies customers over 100, 150, 200, 300
    07-full-run-until-every-place-is-visited/   `scaling` again, with the full run (until every place is visited)
  harness/                 graph builder, validator, runner, experiment definitions, aggregation
    experiments.py           the experiment definitions (the one place to add more)
  algorithms/              one folder per algorithm (algorithm.json + program)
    greedy-insertion/   the original (unregistered) greedy insertion, kept as the reference for the cached version
    greedy-insertion-cached/   Greedy insertion with cache, by Raymond, time O(n^3)
    iterated-local-search/   Iterated local search, by Ben, time O(I * u * m^2)
    nearest-neighbour/   Nearest neighbour (baseline), by Project team, time O(n^2)
  data/                    the dataset files, in the format used
    MY.txt                   GeoNames Malaysia places (read by the harness)
    MY-All-columns_with_header.xlsx   the same data with a header row (for reading in Excel)
    Metadata.txt             field definitions and provenance
    Read Me.txt              the GeoNames readme
  site/                    the results website (serve.py, index.html, css/, js/)
  tests/                   the test suite (python3 -m unittest discover -s tests)
  docs/                    ALGORITHM_SPEC.md, DESIGN.md and the course brief (Project_2627T1.pdf)
```

## Requirements

- Python 3 (developed and tested on Python 3.14). The standard library only: nothing to install.
- Optional: Node.js and Google Chrome, only for the website tests in `tests/`; those tests skip themselves when either is missing.
- A web browser to look at the website. The internet is optional (only for map tiles; the map falls back to a plain drawing offline).

Every command below is run from this `G4T1` folder.

## Run one experiment

```
python3 experiments/01-scaling-number-of-customers/run.py
```

Each experiment folder has its own README (the question, the values, the fixed settings, the exact command, how long it takes, how to read the numbers). Its output is written to `output/` inside that folder. The experiments:

| Folder | Harness experiment | Varies | Values | Examples per value | Fixed |
|---|---|---|---|---|---|
| `01-scaling-number-of-customers` | `scaling` | customers | 5, 10, 15, 20, 30, 50, 100 | 30 | defaults |
| `02-time-budget-travel-period` | `time-budget` | period | 240, 480, 720, 960, 1080 | 30 | customers = 30 |
| `03-speed-travel-speed` | `speed` | speed | 20, 30, 40, 60, 80 | 30 | customers = 30 |
| `04-window-alignment-departure-time` | `window-alignment` | departure | 360, 540, 720, 900, 1080 | 30 | customers = 30, period = 360 |
| `05-spread-customer-radius` | `spread` | radius | 25, 50, 100, 150, 250 | 30 | customers = 20 |
| `06-stress-large-problems` | `stress` | customers | 100, 150, 200, 300 | 10 | defaults |
| `07-full-run-until-every-place-is-visited` | `scaling` (with the full run) | customers | 5, 10, 15, 20, 30, 50, 100 | 30 | defaults |

Folder `07-full-run-until-every-place-is-visited` is the scaling experiment again, with the extra "until every place is visited" view (the first 10 examples of each size are run day after day until every place is served). Folder `01-scaling-number-of-customers` runs scaling first-day only; the full run's output also contains those first-day runs as day 1.

## Run all experiments

```
python3 run_all_experiments.py
```

Runs the experiment folders in order, prints progress and a final summary of where each output is. On the machine that built this submission all of it took about five minutes (each experiment's README gives its own time); a slower machine takes longer.

## Quick check

```
python3 run_all_experiments.py --quick
python3 experiments/01-scaling-number-of-customers/run.py --quick     # one experiment only
```

`--quick` runs only 2 sweep values with 3 examples each (and a 3-example full run for the full-run experiment), so everything can be checked in well under a minute.

## Look at the results on the website

```
python3 site/serve.py --results experiments/01-scaling-number-of-customers/output/results --algorithms algorithms --instances experiments/01-scaling-number-of-customers/output/instances
```

Then open http://127.0.0.1:8000/ (`--port 8001` if busy; Ctrl+C stops it). Use the `output` folder of whichever experiment you ran. `python3 start.py` is the all-in-one alternative: it runs the default scaling evaluation into `results/` and `instances/` here and opens the website (`--sizes 5 10 --instances 3` for a small run; `--suite` for all six experiments; `--help` for the rest). The Compare page needs several experiments' results in one folder, which `start.py --suite` produces.

## Run the tests

```
python3 -m unittest discover -s tests
```

The website tests need Node.js and Chrome and skip without them.

## Add an algorithm

Put it in `algorithms/<your-id>/` with an `algorithm.json` and a program following `docs/ALGORITHM_SPEC.md` (the input and output format, a checklist). The next run picks it up and evaluates only the new algorithm. `docs/DESIGN.md` explains the overall design.

## The data

`data/MY.txt` is the GeoNames dump for Malaysia: tab-separated text, UTF-8, 19 columns, no header row. `data/MY-All-columns_with_header.xlsx` is the same data with a header row, and `data/Metadata.txt` and `data/Read Me.txt` give GeoNames' field definitions. The harness uses these columns: geonameid (1), name (2), latitude (5), longitude (6), feature class (7; only class `P`, populated places, are candidate customers) and population (15). The depot is Kuala Lumpur; customers are a seeded sample of the populated places within a radius of it, and distances are great-circle distances.

## The algorithms included

- `algorithms/greedy-insertion/`: the original (unregistered) greedy insertion, kept as the reference for the cached version. The harness skips it (it has no `algorithm.json`); `compare.py` there compares the two versions.
- `algorithms/greedy-insertion-cached/`: Greedy insertion with cache, by Raymond, time O(n^3). Repeatedly inserts the customer and position that add the least distance.
- `algorithms/iterated-local-search/`: Iterated local search, by Ben, time O(I * u * m^2). Builds a route by inserting the customer and position that push the schedule back the least (time shift, not distance), using cached forward slack for O(1) feasibility checks.
- `algorithms/nearest-neighbour/`: Nearest neighbour (baseline), by Project team, time O(n^2). The baseline every other algorithm is compared against.

## How saved runs are reused (so a rerun is quick)

The harness is incremental. Every run is saved as a file; a saved run is reused when the algorithm's code (a hash of every file in its folder, including `algorithm.json` and so its time limit), the problem and the settings are all unchanged. Running an experiment again therefore prints "Reusing N saved runs, running 0 new". Editing one algorithm re-runs only that algorithm; extra sizes or examples run only the missing ones. `--force` re-runs everything; `--rerun <algorithm-id>` re-runs the named algorithms. Delete an experiment's `output/` folder to start it fresh. Measured runtimes are saved with the run, so they only refresh when an algorithm is re-run.
