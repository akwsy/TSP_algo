# Algorithm Specification

This document tells you, an algorithm author, everything you need to write an algorithm that this project can run, check and compare. You do not need to read any other file in the repository. If something here disagrees with `PROJECT_BRIEF.md`, the brief wins; please report the difference.

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

Default settings: departure 360 (06:00), period 480 minutes (so the deadline is 840, 14:00), speed 40 km/h. Do not hard-code them; read them from the input every time.

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
- **Deterministic:** the same input must always give the same output. If you use randomness, seed your random generator from the `seed` field of the input. Do not seed from the clock.

## 5. Input

The input is one JSON object:

| Field | Meaning |
|---|---|
| `instanceId` | Name of this instance, for example `"n4-seed5"` (4 customers, seed 5). When departure, period or speed differ from the defaults (360, 480, 40) they are appended, for example `"n4-seed5-dep420-per300-spd50"`. |
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
| `stats` | Optional object of numbers describing how much work you did (nodes expanded, iterations, and so on). Used for the "work done" charts. Pick names that make sense for your method. |

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
  "periodMinutes": 480,
  "deadlineMinute": 840,
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

The deadline is 840 (14:00). Customer 2 opens at 1170 (19:30), after the deadline, so no route can include it.

### Output of the baseline

<!-- example:output -->
```json
{"route": [0, 1, 3, 0], "status": "HEURISTIC", "notes": "nearest-neighbour baseline", "stats": {"customersVisited": 2, "iterations": 9}}
```
<!-- /example:output -->

### Replay, step by step

Travel minutes are `km / 40 * 60`, so 1 km takes 1.5 minutes.

1. Leave the depot at **360** (06:00).
2. Depot to customer 1: 47.45 km, 71.18 minutes. Arrive at **431.18** (07:11). Window 360 to 630 is open, so no wait. Leave at 431.18.
3. Customer 1 to customer 3: 92.62 km, 138.94 minutes. Arrive at **570.11** (09:30). Window opens at 630, so **wait 59.89 minutes**. Leave at **630** (10:30), well before the close at 900.
4. Customer 3 to the depot: 132.26 km, 198.39 minutes. Back at **828.39** (13:48), before the deadline of 840. Valid.

<!-- example:schedule -->
| id | name | window | arrive | wait | leave |
|---|---|---|---|---|---|
| 1 | Taman Raja Udang | 360 to 630 | 431.18 | 0.00 | 431.18 |
| 3 | Kampung Sungai Ranggam | 630 to 900 | 570.11 | 59.89 | 630.00 |
<!-- /example:schedule -->

Customer 4 was skipped as well: from customer 1 it is 195.85 km (293.77 minutes) away, so the earliest arrival would be about 724.95, after its window closed at 630. (A different algorithm could go to customer 4 first. Finding better routes than the baseline is the point of the exercise.)

### What the harness records

The harness reports these numbers (rounded here to two decimals; the harness keeps full precision):

<!-- example:result -->
```json
{
  "valid": true,
  "visited": 2,
  "skipped": [2, 4],
  "distanceKm": 272.34,
  "travelMinutes": 408.51,
  "waitMinutes": 59.89,
  "totalMinutes": 468.39,
  "returnMinute": 828.39
}
```
<!-- /example:result -->

`distanceKm` is 47.45 + 92.62 + 132.26. `totalMinutes` is travel plus waiting: 408.51 + 59.89. The score of this run is **2 visits, 272.34 km**.

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

**Run every algorithm**, yours included, on the same instances (one per seed):

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
- [ ] Checked on a few instances with the validator command in section 9.
