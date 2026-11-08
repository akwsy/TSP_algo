# Experiment: spread customer radius

## The question

How does it matter whether the customers are close to the depot or spread far from it?

## What it changes

One thing only: the **radius** [km around the depot], over the values **25, 50, 100, 150, 250**. Every algorithm is run on exactly the same examples at every value, so the algorithms are compared fairly. This is the harness experiment `spread` (defined in `harness/experiments.py`).

The dataset has 544 candidate places within 25 km of Kuala Lumpur (and 1154, 3090, 5212 and 8423 within 50, 100, 150 and 250 km), so every radius can supply the customers.

## Fixed settings

Everything else is the same for every run (the deadline is the departure plus the period, and customers have the four standard time windows between 06:00 and 24:00):

- customers = 20
- period = 1080 minutes (default)
- speed = 40 km/h (default)
- departure = 360 (minutes since midnight) (default)

## Examples per value

30 examples (random problems with seeds 1 to 30) at every value, so 5 x 30 = 150 problems, and every algorithm solves all of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; `-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, departure or radius differs from its default.

| Value | Example names |
|---|---|
| 25 | n20-seed1-rad25, n20-seed2-rad25, n20-seed3-rad25, ..., n20-seed30-rad25 |
| 50 | n20-seed1-rad50, n20-seed2-rad50, n20-seed3-rad50, ..., n20-seed30-rad50 |
| 100 | n20-seed1-rad100, n20-seed2-rad100, n20-seed3-rad100, ..., n20-seed30-rad100 |
| 150 | n20-seed1, n20-seed2, n20-seed3, ..., n20-seed30 |
| 250 | n20-seed1-rad250, n20-seed2-rad250, n20-seed3-rad250, ..., n20-seed30-rad250 |

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/05-spread-customer-radius/run.py
```

This runs `python3 -m harness.experiment spread --results-dir experiments/05-spread-customer-radius/output/results --instances-dir experiments/05-spread-customer-radius/output/instances`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/05-spread-customer-radius/run.py --quick` runs only the values 25 and 50 with 3 examples, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 25 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/05-spread-customer-radius/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-spread.json` (the averages per algorithm and value, plus the pairwise comparisons).
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/05-spread-customer-radius/output/results --algorithms algorithms --instances experiments/05-spread-customer-radius/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
