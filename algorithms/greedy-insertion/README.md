# Greedy insertion, original version (O(n^4)), not registered

This folder keeps the original greedy insertion, a Python port of the team's earlier
`GreedyInsertionSolver.java`, as the reference for `algorithms/greedy-insertion-cached`.

It is **deliberately not run by the harness or shown on the website**: the harness only
picks up folders that contain an `algorithm.json`, and this one has none.

| File | Purpose |
|---|---|
| `solve.py` | The original algorithm. Each try copies the route and replays the whole schedule: O(n) per try, O(n^4) overall. |
| `compare.py` | Runs both versions on the same instances, checks that every route is identical and valid, and prints work and solve time per size. |

## Compare the two versions

From the repository root:

```
python3 algorithms/greedy-insertion/compare.py                    # sizes 5..100, 30 seeds each
python3 algorithms/greedy-insertion/compare.py --sizes 5 10 --seeds 5
```

## To show it on the website later

Add this `algorithm.json` to this folder, commit, and re-run `python3 start.py`:

```json
{
  "id": "greedy-insertion",
  "displayName": "Greedy insertion (original)",
  "author": "Raymond",
  "description": "Repeatedly inserts the customer and position that add the least distance. Every try copies the route and replays the whole schedule to check it.",
  "complexity": { "time": "O(n^4)", "space": "O(n^2)" },
  "exact": false,
  "command": ["python3", "solve.py"],
  "timeLimitSeconds": 10
}
```
