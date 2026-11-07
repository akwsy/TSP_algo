# Project Brief: Routing Algorithm Test Harness and Results Website

> Paste this file into a new chat as the starting context. It is the single source of truth. **Where it conflicts with anything already in the repository (code, README, guides, tickets, old specs), this brief wins.** The only thing carried over from the old repo is the dataset.
>
> Items in section 12 are assumptions the owner has not confirmed. State which assumption you used; do not silently pick one.

Repository: https://github.com/akwsy/TSP_algo

---

## 1. Purpose and roles

Several people will each write their own routing algorithm. This project provides everything around the algorithms:

1. A **specification** (this file, plus a copy in `docs/ALGORITHM_SPEC.md`) telling algorithm authors exactly what input they receive and what output they must produce.
2. A **graph builder** that picks locations from the dataset and builds problem instances.
3. A **test harness** that runs every registered algorithm on the same instances, validates the answers independently, and records results.
4. A **website** that shows those results and the routes on a map, so differences between algorithms can be judged at a glance.

| Who | Responsibility |
|---|---|
| **Owner** | Directs the design, owns the dataset, evaluates the results. |
| **You (new chat)** | Build items 1–4. You do **not** write the competing algorithms (apart from the tiny example in section 7, used only to test the harness). |
| **Algorithm authors** | Write algorithms that follow the specification in section 5. |

## 2. The problem being solved

Given a depot, a departure time, a time period and a set of candidate locations ("customers"), find a round trip that **visits as many distinct customers as possible** within the period.

- The evaluation criterion is **the number of locations visited within the time period.**
- Tie-break: among routes with the same visit count, **the shorter total distance is better.**
- The depot is not counted as a visit.
- Customers are optional; each may be visited at most once.
- The route starts at the depot at the departure time and must return to the same depot no later than `departure + period`.
- Each customer has one **time window**. Arriving early means waiting until it opens. Arriving after it closes is forbidden. Windows are inclusive at both ends.
- Service time at each customer is **zero**.
- Travel, waiting and the return journey all count against the period.
- A route that visits nobody (`depot → depot`) is valid.

## 3. Reset the repository first

Work on a **new branch** (for example `feature/harness-v2`) and open a PR; do not commit to `main` directly.

**Keep (the dataset only):**
- `submission/inputs/MY.txt` (71,709 GeoNames records, tab-separated, no header)
- `submission/inputs/MY-All-columns_with_header.xlsx`
- `docs/Metadata.txt` (field definitions and licence)
- `docs/Read Me.txt` (provenance)

You may move these into a `data/` folder and update paths. Keep the original course brief `docs/Project_2627T1.pdf` as well unless the owner says otherwise.

**Delete everything else:** all old Java code, algorithms, scripts, the old UI, the evaluation and simulation folders, tickets, `PROJECT_GUIDE.md`, `README.md`, `submission/`, golden files and sample scenarios. Write a new `README.md` that matches this brief. Git history preserves the old work; do not port anything from it unless the owner asks.

## 4. The graph builder

### 4.1 Dataset

GeoNames `MY.txt`. Use GeoNameID, name, latitude and longitude. Column order is in `docs/Metadata.txt`. Empty columns must be preserved when parsing; reject malformed rows with a clear message.

### 4.2 Selecting locations

Each instance has one depot and `n` customers, chosen by a **seeded** random selection from the dataset. Same seed and same options must always give the same instance. The default selection rule is in section 12; the selection rule is a replaceable function, not hard-coded across the program.

### 4.3 Time model

All times are **minutes since midnight** on a single day.

**Time range:** the planning day runs from **06:00 to 24:00** (minutes 360 to 1440), which is 18 hours. Divide it **evenly into four slots** of 270 minutes (4 h 30 min):

| Slot | Start | End | Minutes |
|---|---|---|---|
| 0 | 06:00 | 10:30 | 360–630 |
| 1 | 10:30 | 15:00 | 630–900 |
| 2 | 15:00 | 19:30 | 900–1170 |
| 3 | 19:30 | 24:00 | 1170–1440 |

**Every customer is randomly assigned exactly one slot, and its time window is that slot** (inclusive). The assignment is seeded and independent of distance. The depot has no restriction: it is open for the whole day.

### 4.4 Distance and travel time

- Distance between two locations: **haversine**, Earth radius 6371.0088 km, in km.
- Travel time (minutes) = `distanceKm / speedKmh * 60`.
- Default speed: 40 km/h.
- The graph builder computes the full **distance matrix** and gives it to the algorithm, so every algorithm uses identical distances.

### 4.5 Instance parameters

All parameters live in one configuration object, with the defaults below. None is hard-coded elsewhere.

| Parameter | Default | Meaning |
|---|---|---|
| `seed` | required | Drives selection and slot assignment. |
| `numCustomers` | 10 | Customers, not counting the depot. |
| `departureMinute` | 360 (06:00) | Departure time from the depot. |
| `periodMinutes` | 1080 (06:00 to 24:00; the owner changed this default from 480) | Available period. Return must be ≤ `departureMinute + periodMinutes`. |
| `speedKmh` | 40 | Constant travel speed. |

Validity rule: `departureMinute + periodMinutes ≤ 1440`. Reject otherwise.

## 5. Algorithm specification (the contract authors follow)

Put this section, expanded into plain language with a worked example, in `docs/ALGORITHM_SPEC.md`. It must be understandable by someone who has never seen this repo.

### 5.1 How an algorithm is run

Language-agnostic. Each algorithm is a **command-line program**: it reads one instance as JSON from **stdin** and writes one result as JSON to **stdout**. Diagnostics go to stderr. Exit code 0 on a normal answer, nonzero on a crash.

Each algorithm lives in `algorithms/<algorithm-id>/` with an `algorithm.json`:

```json
{
  "id": "greedy-insertion",
  "displayName": "Greedy insertion",
  "author": "Name",
  "description": "One or two sentences on the idea.",
  "complexity": { "time": "O(n^3)", "space": "O(n)" },
  "exact": false,
  "command": ["python3", "solve.py"],
  "timeLimitSeconds": 10
}
```

`complexity` is declared by the author and shown on the website. The harness also **measures** scaling empirically (section 8) and shows both.

### 5.2 Input

```json
{
  "instanceId": "n10-seed42",
  "seed": 42,
  "departureMinute": 360,
  "periodMinutes": 1080,
  "deadlineMinute": 1440,
  "speedKmh": 40,
  "timeLimitSeconds": 10,
  "locations": [
    { "id": 0, "geonameId": 1735161, "name": "Kuala Lumpur", "lat": 3.1412, "lon": 101.6865,
      "isDepot": true,  "opensAt": 0,   "closesAt": 1440 },
    { "id": 1, "geonameId": 1234567, "name": "Example Town", "lat": 3.5, "lon": 101.9,
      "isDepot": false, "opensAt": 630, "closesAt": 900, "slot": 1 }
  ],
  "distanceKm": [[0.0, 52.3], [52.3, 0.0]]
}
```

- `id` is the index into `locations` and into both dimensions of `distanceKm`. **The depot is always id 0.**
- Times are minutes since midnight. `deadlineMinute = departureMinute + periodMinutes`.
- `distanceKm` is symmetric with zeros on the diagonal.
- Travel minutes between `i` and `j` = `distanceKm[i][j] / speedKmh * 60`.

### 5.3 Output

```json
{
  "route": [0, 3, 1, 0],
  "status": "HEURISTIC",
  "notes": "free text, optional",
  "stats": { "nodesExpanded": 1234, "iterations": 56 }
}
```

- `route` is the ordered list of location ids, **starting and ending at 0**. A route that visits nobody is `[0, 0]`.
- The algorithm does **not** report times or distances. The harness computes those itself, so an algorithm cannot misreport.
- `status` is one of:
  - `OPTIMAL`: only if the algorithm proved this is the best possible. An algorithm that stopped on its time limit must **not** claim this.
  - `HEURISTIC`: a feasible answer with no optimality claim.
  - `TIME_LIMIT`: stopped early; `route` is the best found so far.
- `stats` is optional, free-form numbers (nodes expanded, iterations, and so on) used for the "work done" views.

### 5.4 Schedule rules (how the harness replays a route)

Start at the depot at `departureMinute`. For each next location `j` from `i`:

1. `arrive = leave_i + travelMinutes(i, j)`.
2. `start_j = max(arrive, opensAt_j)` (wait if early).
3. If `start_j > closesAt_j` (plus 1e-9 tolerance) the route is **infeasible**.
4. `leave_j = start_j` (zero service time).

After the last customer, return to the depot: `returnTime = leave_last + travelMinutes(last, 0)`. The route is infeasible if `returnTime > deadlineMinute` (plus 1e-9 tolerance).

A route is also infeasible if it: does not start and end at 0, repeats a customer, uses an unknown id, or visits the depot in the middle.

### 5.5 Scoring (what "better" means)

1. More customers visited is better (primary).
2. Equal visits: shorter total distance is better (secondary).
3. An infeasible, malformed, crashed or timed-out-without-output answer scores as a **failure** and is shown as such. It is never silently treated as zero visits.

### 5.6 Requirements for authors

- Deterministic for a given input (if you use randomness, seed it from `seed`).
- Respect `timeLimitSeconds`; the harness kills the process at the limit and records `TIME_LIMIT` with no route if nothing was printed.
- No network access, no reading files other than stdin.

## 6. Harness components

1. **Instance generator.** Builds instances from the dataset and a configuration. Writes `instances/<instanceId>.json` in the format of section 5.2.
2. **Validator.** An **independent** implementation of section 5.4 and 5.5. It recomputes visits, distance, travel time, waiting time, total time and feasibility from the route alone. It must be tested against hand-built valid and invalid routes.
3. **Runner.** For each (algorithm, instance) pair: starts the process, feeds stdin, measures **wall-clock runtime** (the harness measures this, not the algorithm), enforces the time limit, captures output, validates it, records the result.
4. **Experiment definitions** (section 8).
5. **Aggregator.** Averages, standard deviations and comparisons across instances.
6. **Results store.** Plain JSON files in `results/`, one per run, plus an index. The website reads these files. Each run records the algorithm id, the algorithm's **git commit hash** if available, and a timestamp, so results can be compared across algorithm updates.

Re-running is **manual**: one documented command runs everything, and one command starts the website. No CI is required.

### Per-run result record

```json
{
  "runId": "...", "experiment": "scaling", "algorithmId": "greedy-insertion",
  "algorithmCommit": "abc1234", "instanceId": "n10-seed42", "seed": 42, "numCustomers": 10,
  "status": "HEURISTIC", "valid": true, "failureReason": null, "failureKind": null,
  "route": [0, 3, 1, 0],
  "visited": 2, "skipped": [2, 4],
  "distanceKm": 91.4,
  "travelMinutes": 137.1, "waitMinutes": 22.0, "totalMinutes": 159.1,
  "returnMinute": 519.1,
  "runtimeMs": 41.2,
  "stats": { "nodesExpanded": 1234 },
  "schedule": [{ "id": 3, "arriveMinute": 410.2, "startMinute": 410.2, "leaveMinute": 410.2 }]
}
```

`totalMinutes` is travel plus waiting. All fields are computed by the validator, apart from `status`, `stats` and `route`.

## 7. Example algorithm (harness testing only)

Provide one deliberately simple example under `algorithms/example-nearest/` (a nearest-feasible-customer walk), plus the always-`[0,0]` algorithm. Their only purpose is to exercise the harness, tests and website end to end. They are not the competing algorithms and must be labelled as examples. Also include a deliberately **broken** example (infeasible route, malformed JSON, over time limit) used by the harness tests.

## 8. Experiments

Experiments are separate, named, and defined in one place so more can be added later. Only one exists for now.

### Experiment 1: `scaling` (effect of the number of locations)

**Question:** how does each algorithm perform with few locations versus many?

- Vary `numCustomers`. Default sizes: **5, 10, 15, 20, 30, 50, 100** (configurable).
- For each size, generate **30 instances** with different seeds (configurable). **Every algorithm gets the same instances** (paired comparison).
- Period, departure, speed and slot scheme fixed at the defaults in section 4.5 across the whole experiment, so the only variable is size.
- Record per run the metrics in the per-run record.
- Aggregate per (algorithm, size): mean and standard deviation of visited, distance, total minutes, runtime; failure/invalid count; timeout count.
- Also report **relative performance**: for each instance, each algorithm's visits compared with the **best visits any algorithm achieved on that instance** (best-known), averaged per size. Do not call something "optimal" unless an algorithm reported `OPTIMAL`.
- **Empirical scaling:** show how mean runtime and mean work (`stats`) grow with `numCustomers`, alongside the declared complexity. A log-log plot is suitable.

## 9. The website

A new, local, good-looking site. No backend required: static pages reading `results/*.json`, served by one documented command. It must work offline once running, except for optional map tiles (section 9.2).

### 9.1 What it must let the owner see

1. **Overview / comparison.** All algorithms side by side: declared complexity, visited (mean), distance, total time, runtime, failures. Clear ranking by the scoring rule in 5.5.
2. **Experiment view (scaling).** Charts of visits, distance, time and runtime against number of locations, one line per algorithm, with spread (error bars or bands). Plus the empirical scaling plot versus declared complexity.
3. **Instance explorer.** Pick an instance; see every algorithm's answer to it **side by side**: the route on the map, visits, skipped customers, distance, travel/waiting/total minutes, and runtime.
4. **Route detail.** For one run, a step-by-step schedule: location, slot/window, arrival, waiting, departure, cumulative distance, return time.
5. **Run history.** Results labelled by algorithm commit and timestamp, so a change in an algorithm can be compared with its previous version.
6. **Failures.** Invalid, crashed or timed-out runs shown plainly with the reason.

### 9.2 The map

- An attractive, interactive map showing the depot, all candidate locations, and the **routes** as lines in the visiting order, with order numbers.
- Customers coloured by **time slot** (four slots), visited versus skipped clearly distinguished.
- Each algorithm's route in its own colour; toggle algorithms on and off; side-by-side or overlaid.
- Hover or click shows name, window, arrival, wait.
- Use a map library (for example Leaflet or MapLibre) vendored locally or pinned from a CDN. Online tiles are acceptable; if offline, fall back to a plain projected canvas with the same routes so the map never goes blank.

### 9.3 Look and feel

Clean, modern, restrained and **very presentable**: consistent type scale and spacing, a deliberate colour palette that stays legible for colour-blind users, light and dark mode, responsive down to phone width, keyboard operable, readable contrast, no clutter. Quick to scan: the owner should grasp differences between algorithms in seconds. Judge it by looking at screenshots in a real browser, and fix what looks off.

## 10. Tests

Test-first where behaviour must be locked down. At minimum:

- **Graph builder:** deterministic for a seed; depot is id 0; exactly four slots with the exact boundaries in 4.3; every customer has exactly one slot; roughly even slot distribution over large samples; distance matrix symmetric, zero diagonal, matches known haversine values; invalid configs rejected.
- **Validator:** accepts known-good routes; rejects each infeasibility type (late arrival, over deadline, repeated customer, wrong start/end, unknown id); computes waiting and totals correctly against hand-worked examples; boundary cases (arrive exactly at close, return exactly at deadline).
- **Runner:** enforces the time limit, handles crashes, malformed JSON and bad statuses, measures runtime.
- **Aggregator:** averages and best-known comparison on small fixed inputs.
- **Website:** loads the sample results, renders each view without console errors.

Expected values in tests must come from hand-worked examples or the spec, never recomputed with the code under test.

## 11. Working rules

- Ask about anything not specified; list assumptions you make.
- Build only what this brief asks for. No speculative features.
- Keep constants and configuration in one place.
- Report honestly what was verified and what was not. Show test output.
- Commit in small steps on the new branch; open a PR when done.

## 12. Assumptions to confirm with the owner

1. **"6 a.m. to 12 a.m."** is read as 06:00 to midnight (18 h), giving four 4.5-hour slots. If the owner meant 6 a.m. to noon, the slots would be 1.5 hours each. Confirm before building.
2. **Location selection default:** depot = Kuala Lumpur; customers are a seeded random sample of populated places (feature class `P`) within 150 km of the depot, without replacement. Peninsular Malaysia is spread out and a 40 km/h speed makes most far locations unreachable, so a radius keeps instances meaningful. The owner may prefer pure random from the whole dataset or another rule.
3. **Defaults:** departure 06:00, period 1080 min (owner changed from 480), speed 40 km/h, as in 4.5.
4. **"The distance and the distance with travel and the time taken"** is read as: distance travelled (km), travel time (min), and total time taken (travel plus waiting). Confirm if something else was meant.
5. **Experiment 1 sizes and instance count** (5–100 customers, 30 instances each) are proposals.
6. **Algorithm language:** assumed to be language-agnostic (command line, JSON over stdin/stdout). The new program's own language is the new chat's choice; recommend whatever keeps the harness and website simple (for example Python for the harness and plain HTML/JS for the site), and state the choice.
7. **No algorithms are carried over** from the old repo. The three previous algorithms (nearest neighbour, greedy insertion, branch and bound) remain only in git history.
