# Routing Algorithm Test Harness and Results Website

Several people each write a routing algorithm. This repo provides the specification, a graph builder, a test harness that runs and independently validates every algorithm on the same instances, and a static website that shows results and routes on a map. `PROJECT_BRIEF.md` is the source of truth.

**Problem:** from a depot, depart at a given time and return within a period, visiting as many distinct customers as possible, each within its one time window (4 slots over 06:00-24:00). Ties go to shorter distance.

## Layout

| Path | Contents |
|---|---|
| `PROJECT_BRIEF.md` | Full brief (wins over everything else) |
| `data/` | GeoNames Malaysia dataset (`MY.txt`), field definitions and provenance |
| `docs/` | Course brief PDF; `docs/ALGORITHM_SPEC.md` will hold the author-facing spec |
| `harness/` | Python harness (graph builder, validator, runner, aggregator) |
| `tests/` | Test suite |
| `algorithms/`, `instances/`, `results/`, `site/` | Created by later tickets |

Harness: Python 3 (standard library only). Website: plain HTML/JS.

## Run the tests

```
python3 -m unittest discover -s tests
```

## Unconfirmed assumptions (brief section 12)

1. "6 a.m. to 12 a.m." means 06:00 to midnight (18 h), four 4.5 h slots.
2. Default selection: depot Kuala Lumpur, customers a seeded sample of populated places (class `P`) within 150 km, without replacement.
3. Defaults: departure 06:00, period 480 min, speed 40 km/h.
4. Reported metrics: distance (km), travel time, total time (travel plus waiting).
5. Experiment sizes 5, 10, 15, 20, 30, 50, 100 with 30 instances each are proposals.
6. Algorithms are language-agnostic CLI programs (JSON over stdin/stdout); harness in Python, site in plain HTML/JS.
7. No algorithms are carried over from the old repo (history only).
