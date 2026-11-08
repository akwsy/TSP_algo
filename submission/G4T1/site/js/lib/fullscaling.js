// Pure series and wording for the "Until every place is visited" Scaling charts (no DOM).
// Tested by tests/test_site_fullscaling.py. Data: aggregates-<experiment>.json -> full.groups[].
// A size where no instance finished has no point; stopped instances are only ever described in words.

const has = (x) => typeof x === "number" && Number.isFinite(x);

/** One series per algorithm for a full-run metric. `scale` divides the values (e.g. 1000 turns ms into seconds).
 *  lo/hi is mean -/+ std, or null when std is null (n < 2). */
export function fullSeries(full, metric, scale = 1) {
  const byAlg = new Map();
  for (const g of full?.groups || []) {
    const s = g[metric];
    if (!g.finished || !s || !has(s.mean)) continue;
    const std = has(s.std) ? s.std / scale : null;
    const y = s.mean / scale;
    if (!byAlg.has(g.algorithmId)) byAlg.set(g.algorithmId, []);
    byAlg.get(g.algorithmId).push({ x: g.numCustomers, y, mean: y, std, n: s.n ?? null,
      lo: std == null ? null : y - std, hi: std == null ? null : y + std });
  }
  return [...byAlg].sort((a, b) => a[0].localeCompare(b[0]))
    .map(([algorithmId, points]) => ({ algorithmId, points: points.sort((a, b) => a.x - b.x) }));
}

/** Largest group mean of a metric (including its spread is not needed: the axis adds room), or null. */
export function maxMean(groups, metric) {
  const v = (groups || []).filter((g) => g.finished && has(g[metric]?.mean)).map((g) => g[metric].mean);
  return v.length ? Math.max(...v) : null;
}

/** Unit for total compute time, chosen from the largest value in milliseconds so numbers stay readable. */
export function computeUnit(maxMs) {
  if (has(maxMs) && maxMs >= 60000) return { label: "minutes", factor: 60000 };
  if (has(maxMs) && maxMs >= 1000) return { label: "seconds", factor: 1000 };
  return { label: "milliseconds", factor: 1 };
}

const examples = (n) => `${n} example${n === 1 ? "" : "s"}`;

/** Plain-words lines for every algorithm and size that had examples that did not finish. */
export function stoppedNotes(full, nameOf = {}) {
  return (full?.groups || []).filter((g) => g.stopped > 0)
    .sort((a, b) => a.algorithmId.localeCompare(b.algorithmId) || a.numCustomers - b.numCustomers)
    .map((g) => {
      const who = nameOf[g.algorithmId] || g.algorithmId;
      const head = `Not plotted: ${who} had ${examples(g.stopped)} that did not finish at ${g.numCustomers} places.`;
      if (!g.finished) return `${head} No example finished, so there is no point.`;
      return `${head} The line there ${g.finished > 1 ? "averages" : "uses"} the ${g.finished} that finished.`;
    });
}
