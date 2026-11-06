// Pure data logic for the site (no DOM). Tested by tests/test_site_model.py.

const has = (x) => typeof x === "number";

// Ranking rule (brief 5.5): more visits first, then shorter distance.
// Groups with no valid runs (null mean visits) are never treated as zero visits:
// they go last and get no rank. Exact ties share a rank (1, 1, 3).
export function rankGroups(groups) {
  const scored = groups.filter((g) => has(g.visited?.mean));
  const unscored = groups.filter((g) => !has(g.visited?.mean));
  const dist = (g) => (has(g.distanceKm?.mean) ? g.distanceKm.mean : Infinity);
  scored.sort((a, b) => b.visited.mean - a.visited.mean || dist(a) - dist(b)
    || a.algorithmId.localeCompare(b.algorithmId));
  const rows = [];
  scored.forEach((g, i) => {
    const prev = rows[i - 1];
    const tie = prev && prev.visited.mean === g.visited.mean && dist(prev) === dist(g);
    rows.push({ ...g, rank: tie ? prev.rank : i + 1 });
  });
  return [...rows, ...unscored.map((g) => ({ ...g, rank: null }))];
}

export function failureKind(run) {
  if (run.status === "TIME_LIMIT") return "timed out";
  if (/^exited with code/.test(run.failureReason || "")) return "crashed";
  return "invalid";
}

// Invalid runs plus anything the runner killed for time.
export function failedRuns(runs) {
  return runs.filter((r) => r.valid === false || r.status === "TIME_LIMIT");
}
