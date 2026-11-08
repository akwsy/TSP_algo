# Experiment: time budget travel period

## The question

How does the length of the travel period (how long the vehicle may be out, counted from the 06:00 departure) change what the algorithms can visit?

## What it changes

One thing only: the **period** [minutes (from the departure)], over the values **240, 480, 720, 960, 1080**. Every algorithm is run on exactly the same examples at every value, so the algorithms are compared fairly. This is the harness experiment `time-budget` (defined in `harness/experiments.py`).

## Fixed settings

Everything else is the same for every run (the deadline is the departure plus the period, and customers have the four standard time windows between 06:00 and 24:00):

- customers = 30
- speed = 40 km/h (default)
- departure = 360 (minutes since midnight) (default)
- radius = 150 km (default)

## Examples per value

30 examples (random problems with seeds 1 to 30) at every value, so 5 x 30 = 150 problems, and every algorithm solves all of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; `-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, departure or radius differs from its default.

| Value | Example names |
|---|---|
| 240 | n30-seed1-per240, n30-seed2-per240, n30-seed3-per240, ..., n30-seed30-per240 |
| 480 | n30-seed1-per480, n30-seed2-per480, n30-seed3-per480, ..., n30-seed30-per480 |
| 720 | n30-seed1-per720, n30-seed2-per720, n30-seed3-per720, ..., n30-seed30-per720 |
| 960 | n30-seed1-per960, n30-seed2-per960, n30-seed3-per960, ..., n30-seed30-per960 |
| 1080 | n30-seed1, n30-seed2, n30-seed3, ..., n30-seed30 |

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/02-time-budget-travel-period/run.py
```

This runs `python3 -m harness.experiment time-budget --results-dir experiments/02-time-budget-travel-period/output/results --instances-dir experiments/02-time-budget-travel-period/output/instances`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/02-time-budget-travel-period/run.py --quick` runs only the values 240 and 480 with 3 examples, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 40 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/02-time-budget-travel-period/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-time-budget.json` (the averages per algorithm and value, plus the pairwise comparisons).
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/02-time-budget-travel-period/output/results --algorithms algorithms --instances experiments/02-time-budget-travel-period/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
