// Pure data logic for the site (no DOM). Tested by tests/test_site_model.py.

const has = (x) => typeof x === "number";

// Ranking rule (brief 5.5): more visits first, then shorter distance, with one addition:
// algorithms with any failed run rank below every algorithm that was valid on every run, because
// failures are left out of the means and would otherwise flatter them. Each tier is ordered by
// visits, then distance. `rankedBelow` carries the failed-run count so the page can say why.
// Groups with no valid runs (null mean visits) are never treated as zero visits:
// they go last and get no rank. Exact ties share a rank (1, 1, 3).
export function rankGroups(groups) {
  const scored = groups.filter((g) => has(g.visited?.mean));
  const unscored = groups.filter((g) => !has(g.visited?.mean));
  const dist = (g) => (has(g.distanceKm?.mean) ? g.distanceKm.mean : Infinity);
  const failed = (g) => g.failures || 0;
  scored.sort((a, b) => (failed(a) > 0) - (failed(b) > 0) || b.visited.mean - a.visited.mean
    || dist(a) - dist(b) || a.algorithmId.localeCompare(b.algorithmId));
  const rows = [];
  scored.forEach((g, i) => {
    const prev = rows[i - 1];
    const tie = prev && (failed(prev) > 0) === (failed(g) > 0)
      && prev.visited.mean === g.visited.mean && dist(prev) === dist(g);
    rows.push({ ...g, rank: tie ? prev.rank : i + 1, rankedBelow: failed(g) });
  });
  return [...rows, ...unscored.map((g) => ({ ...g, rank: null, rankedBelow: failed(g) }))];
}

// A run the harness killed for exceeding the time limit. A valid route the algorithm itself
// reported as TIME_LIMIT is an ordinary result and is not killed. Older records have no
// `killed` field, so fall back to the recorded reason.
export function wasKilled(run) {
  if (typeof run.killed === "boolean") return run.killed;
  return /exceeded the time limit.*killed$/.test(run.failureReason || "");
}

export function failureKind(run) {
  if (wasKilled(run)) return "timed out";
  if (/^exited with code/.test(run.failureReason || "")) return "crashed";
  return "invalid";
}

// Invalid runs plus anything the harness killed for time.
export function failedRuns(runs) {
  return runs.filter((r) => r.valid === false || wasKilled(r));
}

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Badges for the overview's Failures column: [{ tone: ok|bad|warn|note, text }]. */
export function groupBadges(g) {
  const out = [];
  if (g.failures) {
    out.push({ tone: "bad", text: `${g.failures} of ${g.runs} failed${g.timeouts ? `, ${g.timeouts} killed for time` : ""}` });
    out.push({ tone: "warn", text: `ranked below: ${plural(g.failures, "failed run")}` });
  } else {
    out.push({ tone: "ok", text: "none" });
  }
  if (g.selfReportedTimeLimit) out.push({ tone: "note", text: `${g.selfReportedTimeLimit} reported TIME_LIMIT` });
  if (g.contradictedOptimal) out.push({ tone: "warn", text: `OPTIMAL claim contradicted in ${plural(g.contradictedOptimal, "run")}` });
  return out;
}

/** Short display form of a recorded commit; keeps the "+dirty" marker (uncommitted changes). */
export function shortCommit(commit, length = 7) {
  if (!commit) return null;
  const [hash, ...rest] = String(commit).split("+");
  return [hash.slice(0, length), ...rest].join("+");
}
