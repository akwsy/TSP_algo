# Experiment: stress large problems

## The question

What happens at large sizes: how does the run time grow, how often is the time limit hit, and do any algorithms fail?

## What it changes

One thing only: the **customers** [customers], over the values **100, 150, 200, 300**. Every algorithm is run on exactly the same examples at every value, so the algorithms are compared fairly. This is the harness experiment `stress` (defined in `harness/experiments.py`).

## Fixed settings

Everything else is the same for every run (the deadline is the departure plus the period, and customers have the four standard time windows between 06:00 and 24:00):

- period = 1080 minutes (default)
- speed = 40 km/h (default)
- departure = 360 (minutes since midnight) (default)
- radius = 150 km (default)

## Examples per value

10 examples (random problems with seeds 1 to 10) at every value, so 4 x 10 = 40 problems, and every algorithm solves all of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; `-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, departure or radius differs from its default.

| Value | Example names |
|---|---|
| 100 | n100-seed1, n100-seed2, n100-seed3, ..., n100-seed10 |
| 150 | n150-seed1, n150-seed2, n150-seed3, ..., n150-seed10 |
| 200 | n200-seed1, n200-seed2, n200-seed3, ..., n200-seed10 |
| 300 | n300-seed1, n300-seed2, n300-seed3, ..., n300-seed10 |

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/06-stress-large-problems/run.py
```

This runs `python3 -m harness.experiment stress --results-dir experiments/06-stress-large-problems/output/results --instances-dir experiments/06-stress-large-problems/output/instances`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/06-stress-large-problems/run.py --quick` runs only the values 100 and 150 with 3 examples, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 15 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/06-stress-large-problems/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-stress.json` (the averages per algorithm and value, plus the pairwise comparisons).
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/06-stress-large-problems/output/results --algorithms algorithms --instances experiments/06-stress-large-problems/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
