# Experiment: window alignment departure time

## The question

A short 6-hour period can start at different times of day. How does it matter how the period lines up with the four customer time windows?

## What it changes

One thing only: the **departure** [minutes since midnight, 360 = 06:00], over the values **360, 540, 720, 900, 1080**. Every algorithm is run on exactly the same examples at every value, so the algorithms are compared fairly. This is the harness experiment `window-alignment` (defined in `harness/experiments.py`).

## Fixed settings

Everything else is the same for every run (the deadline is the departure plus the period, and customers have the four standard time windows between 06:00 and 24:00):

- customers = 30
- period = 360 minutes
- speed = 40 km/h (default)
- radius = 150 km (default)

## Examples per value

30 examples (random problems with seeds 1 to 30) at every value, so 5 x 30 = 150 problems, and every algorithm solves all of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; `-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, departure or radius differs from its default.

| Value | Example names |
|---|---|
| 360 | n30-seed1-per360, n30-seed2-per360, n30-seed3-per360, ..., n30-seed30-per360 |
| 540 | n30-seed1-dep540-per360, n30-seed2-dep540-per360, n30-seed3-dep540-per360, ..., n30-seed30-dep540-per360 |
| 720 | n30-seed1-dep720-per360, n30-seed2-dep720-per360, n30-seed3-dep720-per360, ..., n30-seed30-dep720-per360 |
| 900 | n30-seed1-dep900-per360, n30-seed2-dep900-per360, n30-seed3-dep900-per360, ..., n30-seed30-dep900-per360 |
| 1080 | n30-seed1-dep1080-per360, n30-seed2-dep1080-per360, n30-seed3-dep1080-per360, ..., n30-seed30-dep1080-per360 |

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/04-window-alignment-departure-time/run.py
```

This runs `python3 -m harness.experiment window-alignment --results-dir experiments/04-window-alignment-departure-time/output/results --instances-dir experiments/04-window-alignment-departure-time/output/instances`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/04-window-alignment-departure-time/run.py --quick` runs only the values 360 and 540 with 3 examples, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 25 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/04-window-alignment-departure-time/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-window-alignment.json` (the averages per algorithm and value, plus the pairwise comparisons).
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/04-window-alignment-departure-time/output/results --algorithms algorithms --instances experiments/04-window-alignment-departure-time/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
