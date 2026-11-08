# Experiment: full run until every place is visited

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

## The full run ("until every place is visited")

Besides the normal first-day run, the first 10 examples of every size are run again **day after day until every place is visited**: day 1 is the first-day run; each later day the algorithm gets only the places still unvisited (leave 06:00, back by 24:00). It measures the total working hours, days needed and distance, capped at 30 days. Run with `--full-run-instances 10`.

**How this relates to experiment 01.** Experiment 01 runs the same `scaling` experiment first-day only (`--full-run-instances 0`). The output of this experiment contains those first-day runs as day 1 of each full run, plus the later days. If you only want the first-day numbers, 01 is quicker; for the full run use this folder. They write to separate output folders.

## Run it

From the `G4T1` folder (or from anywhere, with the path):

```
python3 experiments/07-full-run-until-every-place-is-visited/run.py
```

This runs `python3 -m harness.experiment scaling --results-dir experiments/07-full-run-until-every-place-is-visited/output/results --instances-dir experiments/07-full-run-until-every-place-is-visited/output/instances --full-run-instances 10`. Extra arguments are passed on to the harness, for example `--instances 5`, or `--force` to ignore saved runs.

**Quick check** (a few seconds): `python3 experiments/07-full-run-until-every-place-is-visited/run.py --quick` runs only the values 5 and 10 with 3 examples and the full run on 3, written to the same `output/` folder (a later full run reuses those runs and does the rest).

**Run time of the full experiment:** about 70 seconds, on the machine that built this submission (a `--quick` run is much faster). Runs already saved in `output/` are reused, so a rerun is quick.

## What is written, and where

Created when you run it, inside `experiments/07-full-run-until-every-place-is-visited/output/` (empty/absent in the submission):

- `results/`: one JSON file per run, `index.json`, and `aggregates-scaling.json` (the averages per algorithm and value, plus the pairwise comparisons), and `sessions/` with one file per algorithm and example for the full run.
- `instances/`: the generated problems, one file each.

## Look at the output on the website

```
python3 site/serve.py --results experiments/07-full-run-until-every-place-is-visited/output/results --algorithms algorithms --instances experiments/07-full-run-until-every-place-is-visited/output/instances
```

Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). Use the toggle in the page header to switch between **First day only** and **Until every place is visited**. Overview ranks the algorithms; Scaling plots them against the swept value; Instance and Route detail show routes on a map; Failures lists runs that were invalid or timed out.

## How to read the main numbers

- **Places visited** (customers served): more is better. This is the main score.
- **Distance (km)**: the tie-break; between equal visits, shorter wins.
- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.
- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time limit; they do not count in the averages.
- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many examples one visited more places than the other.
- **Working hours / days** (full run): total hours of travelling plus waiting until every place is served (nights excluded), and the number of days. Fewer is better; sessions that did not finish are not averaged.
