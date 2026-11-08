#!/usr/bin/env python3
"""(Re)build the course submission folder submission/G4T1/ from this repository.

    python3 submission/build_submission.py              rebuild submission/G4T1 in place
    python3 submission/build_submission.py --check      say whether the committed copy differs from
                                                        what a rebuild would produce (exit 1 if so)
    python3 submission/build_submission.py --out DIR    build into DIR instead (used by the tests)

Standard library only. The copy is self-contained: it holds the code (harness, algorithms, site,
tests, start.py), the data, the docs, and one folder per experiment with a README and a run.py.
The experiment folders are derived from harness/experiments.py, so a new experiment gets a folder
automatically (add a nicer label for it in LABELS below if you like). Rebuild right before submitting.
Rebuilding in place deletes the old G4T1 folder first, including any experiment output inside it.
"""
import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
GROUP = "G4T1"
sys.path.insert(0, str(REPO))
from harness.config import (DEFAULT_DEPARTURE, DEFAULT_PERIOD, DEFAULT_RADIUS_KM,  # noqa: E402
                            DEFAULT_SPEED, InstanceConfig)
from harness.experiments import EXPERIMENTS  # noqa: E402

# Never copied, at any depth (and never compared by --check).
EXCLUDED = {".git", ".claude", ".scratch", "results", "instances", "evaluation", "__pycache__",
            ".DS_Store", "node_modules", "PROJECT_BRIEF.md", "AGENTS.md", "output"}
# Never copied from specific places: this builder's own test (the copy has no builder).
EXCLUDED_FILES = {"tests/test_submission.py"}
EXCLUDED_DIRS = {"docs/agents"}

# Human-readable folder labels, by harness experiment name. Unknown names fall back to
# "<name>-<swept parameter>".
LABELS = {
    "scaling": "scaling-number-of-customers",
    "time-budget": "time-budget-travel-period",
    "speed": "speed-travel-speed",
    "window-alignment": "window-alignment-departure-time",
    "spread": "spread-customer-radius",
    "stress": "stress-large-problems",
}
FULL_RUN_LABEL = "full-run-until-every-place-is-visited"

QUESTIONS = {
    "scaling": "How do the algorithms cope as the number of customers grows? Does the number of places "
               "visited, the distance and the run time change, and how fast does the run time grow?",
    "time-budget": "How does the length of the travel period (how long the vehicle may be out, counted "
                   "from the 06:00 departure) change what the algorithms can visit?",
    "speed": "How does the travel speed change what the algorithms can visit? Slower travel leaves "
             "less time for visiting.",
    "window-alignment": "A short 6-hour period can start at different times of day. How does it matter "
                        "how the period lines up with the four customer time windows?",
    "spread": "How does it matter whether the customers are close to the depot or spread far from it?",
    "stress": "What happens at large sizes: how does the run time grow, how often is the time limit "
              "hit, and do any algorithms fail?",
}
# What to look at first on the website for each experiment's swept parameter.
UNITS = {"customers": "customers", "period": "minutes (from the departure)", "speed": "km/h",
         "departure": "minutes since midnight, 360 = 06:00", "radius": "km around the depot"}
EXTRA_NOTES = {
    "spread": "The dataset has 544 candidate places within 25 km of Kuala Lumpur (and 1154, 3090, 5212 "
              "and 8423 within 50, 100, 150 and 250 km), so every radius can supply the customers.",
}
# Approximate wall-clock time of a full (not --quick) run of this experiment's folder on a laptop.
# Measured on the machine that built the submission; yours will differ. Missing: a generic sentence.
APPROX_TIME = {
    "01-scaling-number-of-customers": "40 seconds",
    "02-time-budget-travel-period": "40 seconds",
    "03-speed-travel-speed": "40 seconds",
    "04-window-alignment-departure-time": "25 seconds",
    "05-spread-customer-radius": "25 seconds",
    "06-stress-large-problems": "15 seconds",
    "07-full-run-until-every-place-is-visited": "70 seconds",
}


def label_for(exp):
    return LABELS.get(exp.name, f"{exp.name}-{exp.param}")


def plan():
    """[(folder name, experiment, with_full_run)] in order: every registry experiment, then the
    full run (scaling with the 'until every place is visited' view)."""
    items = [(exp, False) for exp in EXPERIMENTS.values()]
    full = [e for e in EXPERIMENTS.values() if e.param == "customers" and e.full_run_instances > 0]
    items += [(e, True) for e in full[:1]]
    return [(f"{n:02d}-{FULL_RUN_LABEL if f else label_for(e)}", e, f)
            for n, (e, f) in enumerate(items, start=1)]


# ---------------------------------------------------------------------------------- copying

def excluded(rel):
    parts = Path(rel).parts
    return (any(p in EXCLUDED or p.endswith(".pyc") for p in parts) or rel in EXCLUDED_FILES
            or any(rel == d or rel.startswith(d + "/") for d in EXCLUDED_DIRS))


def copy_tree(src, dst):
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(REPO).as_posix()
        if excluded(rel):
            continue
        target = dst / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def copy_file(rel, out):
    (out / rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / rel, out / rel)


# ---------------------------------------------------------------------------------- run.py

RUN_PY = '''"""Run experiment __NAME__ (__TITLE__).

    python3 experiments/__FOLDER__/run.py            the full experiment
    python3 experiments/__FOLDER__/run.py --quick    a very small run (__QUICK_TEXT__)
    python3 experiments/__FOLDER__/run.py --help     (extra arguments are passed to the harness)

Works from any directory. Output goes into the `output/` folder next to this file:
output/results (one file per run, index.json, aggregates-__NAME__.json__SESSIONS__) and output/instances.
"""
import subprocess
import sys
from pathlib import Path

EXPERIMENT = "__NAME__"
FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]  # the G4T1 folder
BASE = ["-m", "harness.experiment", EXPERIMENT,
        "--results-dir", str(FOLDER / "output" / "results"),
        "--instances-dir", str(FOLDER / "output" / "instances")__FULL__]
QUICK = __QUICK__


def main(argv):
    extra = list(argv)
    quick = "--quick" in extra
    extra = [a for a in extra if a != "--quick"]
    command = [sys.executable] + BASE + (QUICK if quick else []) + extra
    print("Running:", "python3 " + " ".join(command[1:]), flush=True)
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


def quick_args(exp, full):
    vals = [f"{v:g}" for v in exp.values[:2]]
    args = ["--values"] + vals + ["--instances", "3"]
    if full:
        args += ["--full-run-instances", "3"]
    return args


def run_py(folder, exp, full):
    q = quick_args(exp, full)
    quick_text = f"values {q[1]} and {q[2]}, 3 examples" + (", full run on 3" if full else "")
    full_arg = ', "--full-run-instances", "10"' if full else (
        ', "--full-run-instances", "0"' if exp.param == "customers" and exp.full_run_instances > 0 else "")
    sessions = ", output/results/sessions" if full else ""
    return (RUN_PY.replace("__NAME__", exp.name).replace("__TITLE__", folder.split("-", 1)[1])
            .replace("__FOLDER__", folder).replace("__QUICK_TEXT__", quick_text)
            .replace("__SESSIONS__", sessions).replace("__FULL__", full_arg)
            .replace("__QUICK__", repr(q)))


# ---------------------------------------------------------------------------------- experiment README

def fixed_lines(exp):
    """('- customers = 30', ...) for every parameter that is not swept, with its effective value."""
    cfg = exp.config(1, exp.values[0])
    effective = {"customers": (cfg.num_customers, ""), "period": (cfg.period_minutes, " minutes"),
                 "speed": (cfg.speed_kmh, " km/h"), "departure": (cfg.departure_minute, " (minutes since midnight)"),
                 "radius": (cfg.radius_km, " km")}
    defaults = {"period": DEFAULT_PERIOD, "speed": DEFAULT_SPEED, "departure": DEFAULT_DEPARTURE,
                "radius": DEFAULT_RADIUS_KM}
    lines = []
    for key, (val, unit) in effective.items():
        if key == exp.param:
            continue
        note = "" if key in exp.fixed else " (default)" if defaults.get(key) == val or key == "customers" else ""
        lines.append(f"- {key} = {val:g}{unit}{note}")
    return lines


def example_rows(exp, shown=3):
    rows = []
    for v in exp.values:
        ids = [exp.config(s, v).instance_id for s in range(1, min(shown, exp.instances_per_size) + 1)]
        more = ", ..." if exp.instances_per_size > shown else ""
        last = exp.config(exp.instances_per_size, v).instance_id
        rows.append(f"| {v:g} | {', '.join(ids)}{more}, {last} |")
    return rows


def approx_time(folder):
    m = APPROX_TIME.get(folder)
    return (f"about {m}, on the machine that built this submission" if m
            else "depends on your machine")


def experiment_readme(folder, exp, full):
    param = exp.param
    out = f"experiments/{folder}/output"
    vals = ", ".join(f"{v:g}" for v in exp.values)
    n = exp.instances_per_size
    title = folder.split("-", 1)[1].replace("-", " ")
    question = QUESTIONS.get(exp.name, exp.description)
    command = f"python3 experiments/{folder}/run.py"
    serve = (f"python3 site/serve.py --results {out}/results --algorithms algorithms "
             f"--instances {out}/instances")
    harness = (f"python3 -m harness.experiment {exp.name} --results-dir {out}/results "
               f"--instances-dir {out}/instances" + (" --full-run-instances 10" if full else
               " --full-run-instances 0" if exp.param == "customers" and exp.full_run_instances > 0 else ""))
    q = quick_args(exp, full)
    lines = [f"# Experiment: {title}", ""]
    lines += ["## The question", "", question, ""]
    lines += ["## What it changes", "",
              f"One thing only: the **{param}** [{UNITS[param]}], over the values **{vals}**. "
              f"Every algorithm is run on exactly the same examples at every value, so the algorithms "
              f"are compared fairly. This is the harness experiment `{exp.name}` "
              f"(defined in `harness/experiments.py`).", ""]
    if EXTRA_NOTES.get(exp.name):
        lines += [EXTRA_NOTES[exp.name], ""]
    lines += ["## Fixed settings", "",
              "Everything else is the same for every run (the deadline is the departure plus the period, "
              "and customers have the four standard time windows between 06:00 and 24:00):", ""]
    lines += fixed_lines(exp) + [""]
    lines += ["## Examples per value", "",
              f"{n} examples (random problems with seeds 1 to {n}) at every value, so "
              f"{len(exp.values)} x {n} = {len(exp.values) * n} problems, and every algorithm solves all "
              f"of them. An example's name tells you its settings: `n20-seed3` is 20 customers, seed 3; "
              f"`-per480`, `-spd20`, `-dep540` and `-rad50` are added when the period, speed, "
              f"departure or radius differs from its default.", "",
              "| Value | Example names |", "|---|---|"] + example_rows(exp) + [""]
    if full:
        lines += ["## The full run (\"until every place is visited\")", "",
                  "Besides the normal first-day run, the first 10 examples of every size are run again "
                  "**day after day until every place is visited**: day 1 is the first-day run; each "
                  "later day the algorithm gets only the places still unvisited (leave 06:00, back by "
                  "24:00). It measures the total working hours, days needed and distance, capped at 30 "
                  "days. Run with `--full-run-instances 10`.", "",
                  "**How this relates to experiment 01.** Experiment 01 runs the same `scaling` "
                  "experiment first-day only (`--full-run-instances 0`). The output of this experiment "
                  "contains those first-day runs as day 1 of each full run, plus the later days. If you "
                  "only want the first-day numbers, 01 is quicker; for the full run use this folder. "
                  "They write to separate output folders.", ""]
    elif exp.param == "customers" and exp.full_run_instances > 0:
        lines += ["## Relation to the full run", "",
                  f"This folder runs `{exp.name}` first-day only (`--full-run-instances 0`). "
                  f"Experiment {len(EXPERIMENTS) + 1:02d} runs the same experiment and adds the "
                  f"\"until every place is visited\" view (its output contains these first-day runs as "
                  f"day 1).", ""]
    lines += ["## Run it", "", "From the `G4T1` folder (or from anywhere, with the path):", "",
              "```", command, "```", "",
              f"This runs `{harness}`. Extra arguments are passed on to the harness, for example "
              f"`--instances 5`, or `--force` to ignore saved runs.", "",
              f"**Quick check** (a few seconds): `{command} --quick` runs only the values "
              f"{q[1]} and {q[2]} with 3 examples" + (" and the full run on 3" if full else "") +
              ", written to the same `output/` folder (a later full run reuses those runs and does the "
              "rest).", "",
              f"**Run time of the full experiment:** {approx_time(folder)} (a `--quick` run is "
              f"much faster). Runs already saved in `output/` are reused, so a rerun is quick.", ""]
    lines += ["## What is written, and where", "",
              f"Created when you run it, inside `{out}/` (empty/absent in the submission):", "",
              f"- `results/`: one JSON file per run, `index.json`, and `aggregates-{exp.name}.json` "
              f"(the averages per algorithm and value, plus the pairwise comparisons)"
              + (", and `sessions/` with one file per algorithm and example for the full run" if full else "") + ".",
              "- `instances/`: the generated problems, one file each.", ""]
    lines += ["## Look at the output on the website", "", "```", serve, "```", "",
              "Then open http://127.0.0.1:8000/ (add `--port 8001` if 8000 is busy). "
              + ("Use the toggle in the page header to switch between **First day only** and "
                 "**Until every place is visited**. " if full else "")
              + "Overview ranks the algorithms; Scaling plots them against the swept value; Instance and "
                "Route detail show routes on a map; Failures lists runs that were invalid or timed out.", ""]
    lines += ["## How to read the main numbers", "",
              "- **Places visited** (customers served): more is better. This is the main score.",
              "- **Distance (km)**: the tie-break; between equal visits, shorter wins.",
              "- **Runtime (ms)**: how long the algorithm took. Measured, so it varies a little between runs.",
              "- **Failures / timed out**: runs whose answer was invalid, crashed, or exceeded the time "
              "limit; they do not count in the averages.",
              "- **Wins / ties / losses** (in `pairs` of the aggregates file): for two algorithms, on how many "
              "examples one visited more places than the other."]
    if full:
        lines += ["- **Working hours / days** (full run): total hours of travelling plus waiting until every "
                  "place is served (nights excluded), and the number of days. Fewer is better; sessions "
                  "that did not finish are not averaged."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------- run_all_experiments.py

RUN_ALL = '''"""Run every experiment folder in order, one after the other.

    python3 run_all_experiments.py            all experiments (can take a long time)
    python3 run_all_experiments.py --quick    a very small run of each (a few minutes in all)

Extra arguments are passed on to every experiment's run.py. Each experiment writes its own
`output/` folder; the summary at the end says where.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv):
    scripts = sorted((ROOT / "experiments").glob("*/run.py"))
    results = []
    for number, script in enumerate(scripts, start=1):
        print(f"\\n=== [{number}/{len(scripts)}] {script.parent.name} ===", flush=True)
        t0 = time.perf_counter()
        code = subprocess.call([sys.executable, str(script)] + list(argv), cwd=ROOT)
        results.append((script.parent, code, time.perf_counter() - t0))
    print("\\n=== Summary ===")
    for folder, code, secs in results:
        status = "ok" if code == 0 else f"FAILED (exit {code})"
        print(f"{folder.name}: {status}, {secs:.0f} s\\n    output: {folder / 'output'}")
    print("\\nLook at an output on the website, for example:")
    if results:
        out = results[0][0] / "output"
        print(f"  python3 site/serve.py --results {out / 'results'} --algorithms algorithms "
              f"--instances {out / 'instances'}")
    return 0 if all(code == 0 for _, code, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''


# ---------------------------------------------------------------------------------- root README

def algorithm_lines():
    import json
    lines = []
    for d in sorted((REPO / "algorithms").iterdir()):
        if not d.is_dir() or d.name in EXCLUDED:
            continue
        meta = d / "algorithm.json"
        if meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            first = m["description"].split(". ")[0].rstrip(".") + "."
            lines.append(f"- `algorithms/{d.name}/`: {m['displayName']}, by {m['author']}, "
                         f"time {m['complexity']['time']}. {first}")
        else:
            lines.append(f"- `algorithms/{d.name}/`: the original (unregistered) greedy insertion, kept as "
                         "the reference for the cached version. The harness skips it (it has no "
                         "`algorithm.json`); `compare.py` there compares the two versions.")
    return lines


def tree_lines(plans):
    t = [
        "G4T1/",
        "  README.md                this file",
        "  start.py                 run the default evaluation, then open the website",
        "  run_all_experiments.py   run all experiments below, in order (--quick for a small run)",
        "  experiments/             one folder per experiment (README.md + run.py; output/ appears when run)",
    ]
    for folder, exp, full in plans:
        what = ("`scaling` again, with the full run (until every place is visited)" if full
                else f"`{exp.name}`: varies {exp.param} over {', '.join(f'{v:g}' for v in exp.values)}")
        t.append(f"    {folder}/   {what}")
    t += [
        "  harness/                 graph builder, validator, runner, experiment definitions, aggregation",
        "    experiments.py           the experiment definitions (the one place to add more)",
        "  algorithms/              one folder per algorithm (algorithm.json + program)",
    ]
    for a in algorithm_lines():
        t.append("    " + a.split("`")[1].split("/")[1] + "/   " + a.split(": ", 1)[1].split(".")[0])
    t += [
        "  data/                    the dataset files, in the format used",
        "    MY.txt                   GeoNames Malaysia places (read by the harness)",
        "    MY-All-columns_with_header.xlsx   the same data with a header row (for reading in Excel)",
        "    Metadata.txt             field definitions and provenance",
        "    Read Me.txt              the GeoNames readme",
        "  site/                    the results website (serve.py, index.html, css/, js/)",
        "  tests/                   the test suite (python3 -m unittest discover -s tests)",
        "  docs/                    ALGORITHM_SPEC.md, DESIGN.md and the course brief (Project_2627T1.pdf)",
    ]
    return t


def root_readme(plans):
    first_dir = plans[0][0]
    n_exp = len(plans)
    exp_table = ["| Folder | Harness experiment | Varies | Values | Examples per value | Fixed |", "|---|---|---|---|---|---|"]
    for folder, exp, full in plans:
        fixed = ", ".join(f"{k} = {v:g}" for k, v in exp.fixed.items()) or "defaults"
        extra = " (with the full run)" if full else ""
        exp_table.append(f"| `{folder}` | `{exp.name}`{extra} | {exp.param} | "
                         f"{', '.join(f'{v:g}' for v in exp.values)} | {exp.instances_per_size} | {fixed} |")
    return "\n".join([
        "# Routing algorithm experiments (group 4, tutorial 1)",
        "",
        "From a depot, a vehicle leaves at a given time and must return within a period, visiting as many "
        "distinct customers as possible, each within its one time window (four slots over 06:00 to 24:00). "
        "Ties go to the shorter distance. This folder holds three routing algorithms written by the team, a "
        "test harness that builds problems from a real dataset (GeoNames places in Malaysia), runs every "
        "algorithm on the same problems and checks every answer independently, the experiments we present "
        f"({n_exp} folders under `experiments/`), and a website to look at the results. It contains all the "
        "source code and data needed to reproduce the experiments; no saved results are included.",
        "",
        "## Folder structure",
        "",
        "```",
        *tree_lines(plans),
        "```",
        "",
        "## Requirements",
        "",
        "- Python 3 (developed and tested on Python 3.14). The standard library only: nothing to install.",
        "- Optional: Node.js and Google Chrome, only for the website tests in `tests/`; those tests skip "
        "themselves when either is missing.",
        "- A web browser to look at the website. The internet is optional (only for map tiles; the map falls "
        "back to a plain drawing offline).",
        "",
        "Every command below is run from this `G4T1` folder.",
        "",
        "## Run one experiment",
        "",
        "```",
        f"python3 experiments/{first_dir}/run.py",
        "```",
        "",
        "Each experiment folder has its own README (the question, the values, the fixed settings, the exact "
        "command, how long it takes, how to read the numbers). Its output is written to `output/` inside that "
        "folder. The experiments:",
        "",
        *exp_table,
        "",
        f"Folder `{plans[-1][0]}` is the scaling experiment again, with the extra \"until every place is "
        f"visited\" view (the first 10 examples of each size are run day after day until every place is served). "
        f"Folder `{plans[0][0]}` runs scaling first-day only; the full run's output also contains those "
        "first-day runs as day 1.",
        "",
        "## Run all experiments",
        "",
        "```",
        "python3 run_all_experiments.py",
        "```",
        "",
        "Runs the experiment folders in order, prints progress and a final summary of where each output is. "
        "On the machine that built this submission all of it took about five minutes (each experiment's "
        "README gives its own time); a slower machine takes longer.",
        "",
        "## Quick check",
        "",
        "```",
        "python3 run_all_experiments.py --quick",
        f"python3 experiments/{first_dir}/run.py --quick     # one experiment only",
        "```",
        "",
        "`--quick` runs only 2 sweep values with 3 examples each (and a 3-example full run for the full-run "
        "experiment), so everything can be checked in well under a minute.",
        "",
        "## Look at the results on the website",
        "",
        "```",
        f"python3 site/serve.py --results experiments/{first_dir}/output/results --algorithms algorithms "
        f"--instances experiments/{first_dir}/output/instances",
        "```",
        "",
        "Then open http://127.0.0.1:8000/ (`--port 8001` if busy; Ctrl+C stops it). Use the `output` folder of "
        "whichever experiment you ran. `python3 start.py` is the all-in-one alternative: it runs the default "
        "scaling evaluation into `results/` and `instances/` here and opens the website (`--sizes 5 10 "
        "--instances 3` for a small run; `--suite` for all six experiments; `--help` for the rest). The "
        "Compare page needs several experiments' results in one folder, which `start.py --suite` produces.",
        "",
        "## Run the tests",
        "",
        "```",
        "python3 -m unittest discover -s tests",
        "```",
        "",
        "The website tests need Node.js and Chrome and skip without them.",
        "",
        "## Add an algorithm",
        "",
        "Put it in `algorithms/<your-id>/` with an `algorithm.json` and a program following "
        "`docs/ALGORITHM_SPEC.md` (the input and output format, a checklist). The next run picks it up and "
        "evaluates only the new algorithm. `docs/DESIGN.md` explains the overall design.",
        "",
        "## The data",
        "",
        "`data/MY.txt` is the GeoNames dump for Malaysia: tab-separated text, UTF-8, 19 columns, no header row. "
        "`data/MY-All-columns_with_header.xlsx` is the same data with a header row, and `data/Metadata.txt` and "
        "`data/Read Me.txt` give GeoNames' field definitions. The harness uses these columns: geonameid (1), "
        "name (2), latitude (5), longitude (6), feature class (7; only class `P`, populated places, are "
        "candidate customers) and population (15). The depot is Kuala Lumpur; customers are a seeded sample "
        "of the populated places within a radius of it, and distances are great-circle distances.",
        "",
        "## The algorithms included",
        "",
        *algorithm_lines(),
        "",
        "## How saved runs are reused (so a rerun is quick)",
        "",
        "The harness is incremental. Every run is saved as a file; a saved run is reused when the "
        "algorithm's code (a hash of every file in its folder, including `algorithm.json` and so its time "
        "limit), the problem and the settings are all unchanged. Running an experiment again therefore prints "
        "\"Reusing N saved runs, running 0 new\". Editing one algorithm re-runs only that algorithm; extra "
        "sizes or examples run only the missing ones. `--force` re-runs everything; `--rerun <algorithm-id>` "
        "re-runs the named algorithms. Delete an experiment's `output/` folder to start it fresh. Measured "
        "runtimes are saved with the run, so they only refresh when an algorithm is re-run.",
        "",
    ])


# ---------------------------------------------------------------------------------- build

def build(out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for top in ("data", "harness", "algorithms", "site", "tests", "docs"):
        copy_tree(REPO / top, out / top)
    copy_file("start.py", out)
    plans = plan()
    for folder, exp, full in plans:
        d = out / "experiments" / folder
        d.mkdir(parents=True)
        (d / "README.md").write_text(experiment_readme(folder, exp, full), encoding="utf-8")
        (d / "run.py").write_text(run_py(folder, exp, full), encoding="utf-8")
    (out / "run_all_experiments.py").write_text(RUN_ALL, encoding="utf-8")
    (out / "README.md").write_text(root_readme(plans), encoding="utf-8")
    return plans


def files_of(root):
    return {p.relative_to(root).as_posix() for p in Path(root).rglob("*")
            if p.is_file() and not excluded(p.relative_to(root).as_posix())}


def check(target):
    if not target.exists():
        print(f"missing: {target} does not exist; run python3 submission/build_submission.py")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / GROUP
        build(fresh)
        a, b = files_of(fresh), files_of(target)
        problems = [f"missing from the committed copy: {f}" for f in sorted(a - b)]
        problems += [f"only in the committed copy: {f}" for f in sorted(b - a)]
        problems += [f"differs: {f}" for f in sorted(a & b)
                     if not filecmp.cmp(fresh / f, target / f, shallow=False)]
    if problems:
        print(f"{target} differs from a fresh build ({len(problems)} files); rebuild with "
              "python3 submission/build_submission.py")
        print("\n".join(problems[:40]))
        return 1
    print(f"{target} is up to date with the repository.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the course submission folder.")
    ap.add_argument("--check", action="store_true",
                    help="report whether submission/G4T1 differs from a fresh build (exit 1 if so)")
    ap.add_argument("--out", help=f"build into this folder instead of submission/{GROUP}")
    args = ap.parse_args(argv)
    target = Path(args.out) if args.out else HERE / GROUP
    if args.check:
        return check(target)
    plans = build(target)
    print(f"Built {target} with {len(plans)} experiment folders: " + ", ".join(p[0] for p in plans))
    return 0


if __name__ == "__main__":
    sys.exit(main())
