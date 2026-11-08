# Experiment: scaling number of customers

## The question

How do the algorithms cope as the number of customers grows? Does the number of places visited, the distance and the run time change, and how fast does the run time grow?

## What it changes

One thing only: the **customers** [customers], over the values **5, 10, 15, 20, 30, 50, 100**. Every algorithm is run on exactly the same examples at every value, so the algorithms are compared fairly. This is the harness experiment `scaling` (defined in `harness/experiments.py`).

## Fixed settings

Everything else is the same for every run (the deadline is the departure plus the period, and customers have the four standard time windows between 06:00 and 24:00):

- period = 1080 minutes (default)
- speed = 40 km/h (default)
- departure = 360 (minutes since midnight) (default)
- radius = 150 km (default)

## Examples per value

30 examples (random problems with seeds 1 to 30) at every value, so 7 x 30 = 210 problems, and every algorithm solves all of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; `-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, departure or radius differs from its default.

| Value | Example names |
|---|---|
| 5 | n5-seed1, n5-seed2, n5-seed3, ..., n5-seed30 |
| 10 | n10-seed1, n10-seed2, n10-seed3, ..., n10-seed30 |
| 15 | n15-seed1, n15-seed2, n15-seed3, ..., n15-seed30 |
| 20 | n20-seed1, n20-seed2, n20-seed3, ..., n20-seed30 |
| 30 | n30-seed1, n30-seed2, n30-seed3, ..., n30-seed30 |
| 50 | n50-seed1, n50-seed2, n50-seed3, ..., n50-seed30 |
| 100 | n100-seed1, n100-seed2, n100-seed3, ..., n100-seed30 |

## Relation to the full run

This folder runs `scaling` first-day only (`--full-run-instances 0`). Experiment 07 runs the same experiment and adds the "until every place is visited" view (its output contains these first-day runs as day 1).

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/01-scaling-number-of-customers/run.py
```

This runs `python3 -m harness.experiment scaling --results-dir experiments/01-scaling-number-of-customers/output/results --instances-dir experiments/01-scaling-number-of-customers/output/instances --full-run-instances 0`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/01-scaling-number-of-customers/run.py --quick` runs only the values 5 and 10 with 3 examples, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 40 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/01-scaling-number-of-customers/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-scaling.json` (the averages per algorithm and value, plus the pairwise comparisons).
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/01-scaling-number-of-customers/output/results --algorithms algorithms --instances experiments/01-scaling-number-of-customers/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
