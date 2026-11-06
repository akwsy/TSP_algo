# Algorithm Specification

This document tells you, an algorithm author, everything you need to write an algorithm that this project can run, check and compare. You do not need to read the harness or website code to write one, but you do need a checkout of this repository to run and check your algorithm (section 9). If something here disagrees with `PROJECT_BRIEF.md`, the brief wins; please report the difference.

## Start here: instructions for AI coding agents (and developers using them)

If you are an AI coding agent and a developer has asked you to implement an algorithm "per this specification", this section is your task description. Follow it exactly.

**What to deliver.** One new folder, `algorithms/<algorithm-id>/`, containing only:

- `algorithm.json`, filled in completely (section 3), with honest `complexity` and `exact` values;
- your program (for example `solve.py`), written to the rules in sections 4 to 7.

**What not to touch.** Do not edit anything outside your own folder: not `harness/`, `site/`, `docs/`, `tests/`, `README.md`, and not another algorithm's folder. If you think the harness or this document is wrong, say so in your final report instead of changing it.

**Language and dependencies.** Use the language the developer asks for. If they do not say, use Python 3 with the standard library only, so the program runs anywhere the harness runs. If you must use a third-party package or a compiled program, say so plainly in `algorithm.json`'s `description` and in your report, because the harness does not install anything.

**Rules that are easy to get wrong** (each is explained below; the harness checks them):

1. Read only stdin, print exactly one JSON object to stdout, send everything else to stderr, and exit with code 0.
2. Use the given `distanceKm` matrix and read departure, deadline and speed from the input. Never hard-code them.
3. Same input must give byte-identical output. Seed any randomness from the input's `seed`. **Do not stop your search by the clock if you want identical output**: stop after a fixed amount of work (a fixed number of restarts or iterations). If you do cap by the clock as a safety net, set `status` to `TIME_LIMIT` when the cap is what stopped you, and know that results can then differ between runs.
4. Report `OPTIMAL` only if you completed an exhaustive search that proves it. Otherwise `HEURISTIC`, or `TIME_LIMIT` if you stopped early.
5. Put your main "amount of work" counter in `stats` under the name `iterations` or `nodesExpanded`. Other names are stored but only these two feed the website's work chart. Do not put times or other values that change between runs into `stats` or `notes`.
6. Return `[0, 0]` when nothing can be served. Never output an invalid route; if in doubt, drop the last stop.
7. Your program must handle 5 to 100 customers and finish well inside `timeLimitSeconds` (keep it at the default 10 unless the developer says otherwise).

**How to check your work before reporting done** (commands are in section 9; do all of them):

1. Run your program by hand on a 5-customer and a 100-customer instance and validate the routes with the validator command.
2. Run it twice on the same instance and confirm the two outputs are identical.
3. Run `python3 -m harness.experiment scaling --sizes 5 20 100 --instances 5` and confirm that **every one of your runs is valid** (no `FAILED` lines) and none is slower than a few seconds.
4. Compare your visit counts with the baseline `nearest-neighbour` in the same output. You do not have to beat it, but if you are far worse, look for a bug.

**What to put in your final report.** The folder you created; how the algorithm works in two or three sentences; the declared complexity and why; what you ran and the real results (validity, determinism, runtimes, visits next to the baseline); anything you were unsure about or that this document did not cover. Do not claim a check you did not run.

## 1. The problem

You are given a **depot** (always Kuala Lumpur with the default settings), a **departure time**, a **time period**, and a list of **customers** (towns and villages in Malaysia). Plan one round trip:

- Leave the depot at the departure time.
- Visit some of the customers, each **at most once**. Visiting a customer is optional.
- Come back to the same depot **no later than departure + period** (the *deadline*).

Each customer has one **time window**, an opening minute and a closing minute. You may arrive early and wait until it opens. You may not arrive after it closes. There is no service time: as soon as a customer is open, you visit it and leave immediately.

Travel, waiting and the trip back to the depot all use up the period.

### Scoring

1. **More customers visited is better.** This is the main criterion. The depot does not count.
2. **If two routes visit the same number of customers, the shorter total distance is better.**
3. A route that breaks any rule, output that cannot be read, a crash, or a timeout with no answer is a **failure**. A failure is shown as a failure, never as "zero visits".

A route that visits nobody (`[0, 0]`, straight home) is valid and scores zero visits. When nothing is reachable, that is the right answer.

## 2. Time, distance and slots

- All times are **minutes since midnight** on a single day. `360` is 06:00, `840` is 14:00, `1440` is midnight at the end of the day.
- The planning day runs from 06:00 to 24:00 and is split into four equal **slots** of 270 minutes. Every customer gets exactly one slot, chosen at random, and its time window is that slot:

| Slot | Window (minutes) | Clock time |
|---|---|---|
| 0 | 360 to 630 | 06:00 to 10:30 |
| 1 | 630 to 900 | 10:30 to 15:00 |
| 2 | 900 to 1170 | 15:00 to 19:30 |
| 3 | 1170 to 1440 | 19:30 to 24:00 |

- The depot is open all day (0 to 1440).
- You are given the full **distance matrix** in kilometres (great-circle distance). Use it; do not compute your own distances. Everyone then works with exactly the same numbers.
- Travel time in minutes between locations `i` and `j` is:

  `travelMinutes(i, j) = distanceKm[i][j] / speedKmh * 60`

Default settings: departure 360 (06:00), period 1080 minutes (so the deadline is 1440, 24:00), speed 40 km/h. Do not hard-code them; read them from the input every time.

## 3. Your algorithm folder

Your algorithm is a **command-line program** in any language. Put it in its own folder:

```
algorithms/<your-algorithm-id>/
    algorithm.json      (required, described below)
    solve.py            (or whatever your program is)
```

The harness finds every `algorithms/*/algorithm.json` and runs each one. Use the same id for the folder name and the `id` field.

### `algorithm.json`

This is the real file of the baseline algorithm that ships with the repository (`algorithms/nearest-neighbour/algorithm.json`):

```json
{
  "id": "nearest-neighbour",
  "displayName": "Nearest neighbour (baseline)",
  "author": "Project team",
  "description": "The baseline every other algorithm is compared against. From the depot, repeatedly go to the nearest customer that can still be served within its window and leaves time to return before the deadline; ties go to the lowest id.",
  "complexity": { "time": "O(n^2)", "space": "O(n)" },
  "exact": false,
  "command": ["python3", "solve.py"],
  "timeLimitSeconds": 10
}
```

| Field | Meaning |
|---|---|
| `id` | Short unique id, lowercase with hyphens. Same as the folder name. Appears in every result. |
| `displayName` | Human-readable name for the website. |
| `author` | Your name. |
| `description` | One or two sentences on the idea. |
| `complexity` | Your declared time and space complexity, as text (for example `"O(n^3)"`). Shown on the website next to the scaling the harness measures. |
| `exact` | `true` if your method is designed to find a proven best route (for example branch and bound); `false` for a heuristic. |
| `command` | The command that starts your program, as a list of arguments (not one shell string). It is run **with your algorithm folder as the working directory**, so `["python3", "solve.py"]` runs `solve.py` from your folder. A compiled program might use `["./solve"]`. |
| `timeLimitSeconds` | How long your program may run on one instance, in seconds. If you leave it out, the harness uses 10. |

The harness needs `id` and `command` to run anything; fill in all fields so the website can show them.

## 4. How your program is run

For each instance, the harness:

1. Starts your `command` in your folder.
2. Writes **one instance as JSON to your standard input** (stdin), then closes it.
3. Waits for your program to exit, up to `timeLimitSeconds`.
4. Reads **one result as JSON from your standard output** (stdout).
5. Replays your route itself (section 7) to decide whether it is valid and to compute every number.

Rules:

- **stdout** must contain exactly one JSON object and nothing else. No progress messages, no banners.
- **stderr** is for your diagnostics (debug prints, progress). It never affects your score; the harness saves it in the run's result file so you can read it when debugging.
- **Exit code 0** means "here is my answer". Any **nonzero** exit code means "I crashed"; the run is recorded as a failure (`exited with code N`) even if you printed something.
- If stdout is not valid JSON, is not a JSON object, has a `status` that is not one of the three values in section 6, or has a `stats` that is not an object, the run is a failure with that reason (for example `output is not valid JSON` or `unknown status 'DONE'`).
- **Time limit:** the limit is wall-clock time for the whole process, including start-up (for example, starting the Python interpreter). If your program is still running at the limit, the harness kills it, records the status as `TIME_LIMIT` whatever you claimed, and notes `exceeded the time limit of N s and was killed`. If you had already printed a complete result object, that route is still replayed and scored; otherwise the run is a failure with no route. Only runs the harness killed count as timeouts. A valid route you print yourself with `status` `TIME_LIMIT` is an ordinary result and is not listed as a failure. Do not rely on being killed: **print your best answer and exit before the limit** (with `status` `TIME_LIMIT` if you stopped early; see section 6).
- **No network access** and **no reading files** other than stdin. Everything you need is in the input.
- **Deterministic:** the same input must always give the same output. If you use randomness, seed your random generator from the `seed` field of the input. Do not seed from the clock. Also do not let the clock decide how much work you do: "search for 2 seconds" gives different answers on a faster or slower machine. Stop after a fixed number of iterations or restarts instead. If you add a clock-based cap only as a safety net, report `TIME_LIMIT` when it is what stopped you.
- **Dependencies:** the harness only runs your `command`; it does not install anything. Prefer the language's standard library. Anything else must be stated in your `description`.
- **Commit your folder** before you run the official experiment. The harness records the git commit of your folder with every result; uncommitted changes are marked `+dirty` and shown as a separate version on the website's history page.

## 5. Input

The input is one JSON object:

| Field | Meaning |
|---|---|
| `instanceId` | Name of this instance, for example `"n4-seed5"` (4 customers, seed 5). When departure, period or speed differ from the defaults (360, 1080, 40) they are appended, for example `"n4-seed5-dep420-per300-spd50"`. |
| `seed` | The seed the instance was generated from. Use it to seed any randomness you need. |
| `departureMinute` | When you leave the depot. |
| `periodMinutes` | How long you have. |
| `deadlineMinute` | `departureMinute + periodMinutes`. You must be back at the depot by then. |
| `speedKmh` | Constant travel speed. |
| `timeLimitSeconds` | The limit declared in your `algorithm.json` (10 if you left it out), added by the harness at run time so you can plan your search. It is not part of the worked example below, which shows the generated instance only. |
| `locations` | List of locations. See below. |
| `distanceKm` | Square matrix of distances in km. `distanceKm[i][j]` is the distance from location `i` to location `j`. It is symmetric with zeros on the diagonal. |

Each entry in `locations`:

| Field | Meaning |
|---|---|
| `id` | The location's index in `locations` and in both dimensions of `distanceKm`. **The depot is always id 0**; customers are 1, 2, 3, ... |
| `geonameId`, `name`, `lat`, `lon` | Where it is (from the GeoNames dataset). You do not need these to solve the problem. |
| `isDepot` | `true` only for id 0. |
| `opensAt`, `closesAt` | The time window in minutes, **inclusive at both ends**. |
| `slot` | Customers only: which slot (0 to 3) the window comes from. Purely informative; `opensAt` and `closesAt` already say everything. |

## 6. Output

Print one JSON object:

```json
{
  "route": [0, 3, 1, 0],
  "status": "HEURISTIC",
  "notes": "free text, optional",
  "stats": { "nodesExpanded": 1234, "iterations": 56 }
}
```

| Field | Meaning |
|---|---|
| `route` | Required. The location ids in visiting order, **starting and ending with 0**. Each customer appears at most once and the depot appears only at the two ends. Visiting nobody is `[0, 0]`. Use plain integers (`3`, not `3.0` or `"3"`). |
| `status` | Required. One of `OPTIMAL`, `HEURISTIC`, `TIME_LIMIT` (below). |
| `notes` | Optional free text for humans. |
| `stats` | Optional object of numbers describing how much work you did. The "work done" charts use `nodesExpanded` if you report it, otherwise `iterations`; put your main work counter under one of those two names. Any other numbers you add (for example `restarts`) are stored with the run but are not charted. Do not put anything in `stats` that changes between runs of the same input, such as seconds. |

**Do not report times, distances or visit counts.** The harness computes all of them from your route, so they cannot be misreported. Extra fields such as `"distanceKm"` are ignored.

### What the status values mean

- **`OPTIMAL`**: you have **proved** that no valid route visits more customers, or visits as many with a shorter distance. Only exact methods that finished their search may say this. If you stopped because of your time limit, you must not claim `OPTIMAL`. The website flags a claim as contradicted when another valid run on the same instance visited more customers.
- **`HEURISTIC`**: a valid answer with no claim of being the best. Most algorithms report this.
- **`TIME_LIMIT`**: you stopped early because time was running out, and `route` is the best you had found so far.

The status is your claim; the harness checks the route itself either way. The website calls something optimal only if an algorithm reported `OPTIMAL`.

## 7. How the harness replays your route

The harness walks your route from start to end. Start at the depot at `departureMinute`. For each next location `j`, coming from location `i`:

1. **Arrive:** `arrive = leave_i + travelMinutes(i, j)`.
2. **Wait if early:** `start_j = max(arrive, opensAt_j)`.
3. **Forbidden if late:** if `start_j > closesAt_j + 0.000000001`, the route is **invalid**. Arriving at exactly `closesAt_j` is allowed (the window is inclusive).
4. **Leave immediately:** `leave_j = start_j` (zero service time).

After the last customer, drive back: `returnTime = leave_last + travelMinutes(last, 0)`. The route is **invalid** if `returnTime > deadlineMinute + 0.000000001`. Returning at exactly the deadline is allowed.

The tiny tolerance (1e-9 minutes) only absorbs floating-point rounding. Compute travel times exactly as in section 2, with the matrix you were given, and your own feasibility checks will agree with the harness.

A route is also **invalid** if it:

- does not start with 0, or does not end with 0;
- visits the depot (0) in the middle;
- visits a customer more than once;
- uses an id that is not in `locations`;
- is not a list, or has fewer than two entries.

From a valid route the harness computes: customers visited, customers skipped, total distance (km), travel minutes, waiting minutes, total minutes (travel plus waiting), return minute, and a stop-by-stop schedule.

## 8. Worked example

This is a real instance produced by the project's graph builder (`--seed 5 --customers 4`), the real answer of the baseline algorithm, and the numbers the harness's validator computes for it. The repository's tests check that every number below matches the code.

### Input

<!-- example:input -->
```json
{
  "instanceId": "n4-seed5",
  "seed": 5,
  "departureMinute": 360,
  "periodMinutes": 1080,
  "deadlineMinute": 1440,
  "speedKmh": 40.0,
  "locations": [
    {"id": 0, "geonameId": 1735161, "name": "Kuala Lumpur", "lat": 3.1412, "lon": 101.68653,
     "isDepot": true, "opensAt": 0, "closesAt": 1440},
    {"id": 1, "geonameId": 12746846, "name": "Taman Raja Udang", "lat": 3.30007, "lon": 101.28984,
     "isDepot": false, "opensAt": 360, "closesAt": 630, "slot": 0},
    {"id": 2, "geonameId": 1768785, "name": "Kampung Jeragan", "lat": 3.4856, "lon": 102.1389,
     "isDepot": false, "opensAt": 1170, "closesAt": 1440, "slot": 3},
    {"id": 3, "geonameId": 7565878, "name": "Kampung Sungai Ranggam", "lat": 4.0393, "lon": 100.9051,
     "isDepot": false, "opensAt": 630, "closesAt": 900, "slot": 1},
    {"id": 4, "geonameId": 7797539, "name": "Kemajuan Tanah Selancar Enam", "lat": 2.6933, "lon": 102.9456,
     "isDepot": false, "opensAt": 360, "closesAt": 630, "slot": 0}
  ],
  "distanceKm": [
    [0.0, 47.451234145176535, 63.15310334482244, 132.26182998024285, 148.42595395769408],
    [47.451234145176535, 0.0, 96.47726640161441, 92.62472737632565, 195.84834886780092],
    [63.15310334482244, 96.47726640161441, 0.0, 150.1042605946633, 125.63584985287612],
    [132.26182998024285, 92.62472737632565, 150.1042605946633, 0.0, 271.48013918706766],
    [148.42595395769408, 195.84834886780092, 125.63584985287612, 271.48013918706766, 0.0]
  ]
}
```
<!-- /example:input -->

The deadline is 1440 (24:00), so every window fits inside the period. Customer 2 opens late, at 1170 (19:30), so a route that visits it spends a long time waiting.

### Output of the baseline

<!-- example:output -->
```json
{"route": [0, 1, 3, 2, 0], "status": "HEURISTIC", "notes": "nearest-neighbour baseline", "stats": {"customersVisited": 3, "iterations": 10}}
```
<!-- /example:output -->

### Replay, step by step

Travel minutes are `km / 40 * 60`, so 1 km takes 1.5 minutes.

1. Leave the depot at **360** (06:00).
2. Depot to customer 1: 47.45 km, 71.18 minutes. Arrive at **431.18** (07:11). Window 360 to 630 is open, so no wait. Leave at 431.18.
3. Customer 1 to customer 3: 92.62 km, 138.94 minutes. Arrive at **570.11** (09:30). Window opens at 630, so **wait 59.89 minutes**. Leave at **630** (10:30), well before the close at 900.
4. Customer 3 to customer 2: 150.10 km, 225.16 minutes. Arrive at **855.16** (14:15). Window opens at 1170, so **wait 314.84 minutes**. Leave at **1170** (19:30), well before the close at 1440.
5. Customer 2 to the depot: 63.15 km, 94.73 minutes. Back at **1264.73** (21:04), before the deadline of 1440. Valid.

<!-- example:schedule -->
| id | name | window | arrive | wait | leave |
|---|---|---|---|---|---|
| 1 | Taman Raja Udang | 360 to 630 | 431.18 | 0.00 | 431.18 |
| 3 | Kampung Sungai Ranggam | 630 to 900 | 570.11 | 59.89 | 630.00 |
| 2 | Kampung Jeragan | 1170 to 1440 | 855.16 | 314.84 | 1170.00 |
<!-- /example:schedule -->

Customer 4 was skipped: from customer 1 it is 195.85 km (293.77 minutes) away, so the earliest arrival would be about 724.95, after its window closed at 630. (A different algorithm could go to customer 4 first. Finding better routes than the baseline is the point of the exercise.)

### What the harness records

The harness reports these numbers (rounded here to two decimals; the harness keeps full precision):

<!-- example:result -->
```json
{
  "valid": true,
  "visited": 3,
  "skipped": [4],
  "distanceKm": 353.33,
  "travelMinutes": 530.0,
  "waitMinutes": 374.73,
  "totalMinutes": 904.73,
  "returnMinute": 1264.73
}
```
<!-- /example:result -->

`distanceKm` is 47.45 + 92.62 + 150.10 + 63.15. `totalMinutes` is travel plus waiting: 530.00 + 374.73. The score of this run is **3 visits, 353.33 km**.

## 9. Running your algorithm locally

You need Python 3 for the harness (standard library only). From the repository root:

**Make an instance file.** `--seed` is required; the other options default to the values in section 2.

```
python3 -m harness.generate_instance --seed 5 --customers 4 --out instances/n4-seed5.json
```

Other options: `--departure` (minute), `--period` (minutes), `--speed` (km/h). Departure plus period may not exceed 1440.

**Run your program on it by hand**, from your folder, exactly as the harness does:

```
cd algorithms/<your-algorithm-id>
python3 solve.py < ../../instances/n4-seed5.json
```

**Check the answer with the harness's validator**, from the repository root (replace the route with yours):

```
python3 -c "import json; from harness.validator import validate_route; inst = json.load(open('instances/n4-seed5.json')); print(json.dumps(validate_route(inst, [0, 1, 3, 0]), indent=2))"
```

If `valid` is `false`, `failureReason` says why (for example `arrived late at location 4: ...`).

**Check a large instance and determinism.** Make a 100-customer instance, run your program twice on it, and confirm the two outputs are identical and appear quickly:

```
python3 -m harness.generate_instance --seed 7 --customers 100 --out instances/n100-seed7.json
cd algorithms/<your-algorithm-id>
python3 solve.py < ../../instances/n100-seed7.json > /tmp/out-a.json
python3 solve.py < ../../instances/n100-seed7.json > /tmp/out-b.json
diff /tmp/out-a.json /tmp/out-b.json && echo identical
```

**Run the real comparison.** This runs every algorithm, yours included, on the same sets of 5, 20 and 100 customers and prints one line per run. Every line for your algorithm should say `valid`:

```
python3 -m harness.experiment scaling --sizes 5 20 100 --instances 5
```

**Run every algorithm** on specific instances (one per seed) without the experiment:

```
python3 -m harness.run --seeds 1 2 3 --customers 10
```

This writes the instances to `instances/`, one result file per (algorithm, instance) to `results/`, updates `results/index.json`, and prints one line per run, such as `nearest-neighbour on n10-seed1: valid, visited 4` or `... FAILED: <reason>`.

## 10. Checklist

- [ ] Folder `algorithms/<id>/` with an `algorithm.json` whose `id` matches the folder name.
- [ ] `command` is a list of arguments and works when run from your folder.
- [ ] Reads one JSON instance from stdin; reads no other files; uses no network.
- [ ] Uses the given `distanceKm` matrix and `travelMinutes = km / speedKmh * 60`; reads departure, deadline and speed from the input.
- [ ] Prints exactly one JSON object to stdout; diagnostics go to stderr only.
- [ ] `route` starts and ends with 0, has no repeats, no depot in the middle; `[0, 0]` if nothing fits.
- [ ] Every stop respects its window (wait if early, never late) and the return is by `deadlineMinute`.
- [ ] `status` is `OPTIMAL` only with proof, `TIME_LIMIT` if you stopped early, otherwise `HEURISTIC`.
- [ ] Same input gives the same output; any randomness is seeded from `seed`.
- [ ] Prints its answer and exits with code 0 before `timeLimitSeconds`.
- [ ] Stops after a fixed amount of work, not by the clock (or reports `TIME_LIMIT` if a clock cap stopped it).
- [ ] Main work counter is in `stats` as `iterations` or `nodesExpanded`; no run-to-run varying values in `stats` or `notes`.
- [ ] Nothing outside `algorithms/<id>/` was changed.
- [ ] Checked on a few instances with the validator command in section 9, including a 100-customer instance run twice with identical output.
- [ ] `python3 -m harness.experiment scaling --sizes 5 20 100 --instances 5` shows only valid runs for your algorithm.
- [ ] Folder committed to git.
