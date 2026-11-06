// Pure data logic for the scaling charts and run history (no DOM). Tested by tests/test_site_scaling.py.

const has = (x) => typeof x === "number" && Number.isFinite(x);

/** Series for one metric: one per algorithm, points sorted by customers. Groups with a null mean are left out.
 *  lo/hi is mean -/+ std, or null when std is null (n < 2). */
export function buildSeries(groups, metric) {
  const byAlg = new Map();
  for (const g of groups) {
    const s = g[metric];
    if (!s || !has(s.mean)) continue;
    const std = has(s.std) ? s.std : null;
    if (!byAlg.has(g.algorithmId)) byAlg.set(g.algorithmId, []);
    byAlg.get(g.algorithmId).push({
      x: g.numCustomers, mean: s.mean, std, n: s.n ?? null,
      lo: std == null ? null : s.mean - std, hi: std == null ? null : s.mean + std,
    });
  }
  return [...byAlg].sort((a, b) => a[0].localeCompare(b[0]))
    .map(([algorithmId, points]) => ({ algorithmId, points: points.sort((a, b) => a.x - b.x) }));
}

/** Least-squares slope of log y against log x: the measured growth exponent. null with fewer than 2 distinct sizes. */
export function fitSlope(points) {
  const p = points.filter((q) => q.x > 0 && q.y > 0);
  if (new Set(p.map((q) => q.x)).size < 2) return null;
  const xs = p.map((q) => Math.log(q.x)), ys = p.map((q) => Math.log(q.y));
  const mx = xs.reduce((a, b) => a + b) / xs.length, my = ys.reduce((a, b) => a + b) / ys.length;
  let num = 0, den = 0;
  xs.forEach((x, i) => { num += (x - mx) * (ys[i] - my); den += (x - mx) ** 2; });
  return num / den;
}

/** Log-log data for runtimeMs or work. Log axes cannot show zero or missing values, so those sizes are
 *  reported in `skipped` instead of being drawn. For work, `key` is the stat name the harness used. */
export function logLogSeries(groups, metric) {
  const out = new Map();
  for (const g of groups) {
    if (!out.has(g.algorithmId)) out.set(g.algorithmId, { algorithmId: g.algorithmId, key: null, points: [], skipped: [] });
    const e = out.get(g.algorithmId);
    const s = g[metric];
    if (metric === "work" && s?.key) e.key = s.key;
    if (s && has(s.mean) && s.mean > 0 && g.numCustomers > 0) e.points.push({ x: g.numCustomers, y: s.mean, n: s.n ?? null });
    else e.skipped.push(g.numCustomers);
  }
  return [...out.values()].sort((a, b) => a.algorithmId.localeCompare(b.algorithmId))
    .map((e) => {
      const points = e.points.sort((a, b) => a.x - b.x);
      return { ...e, points, skipped: e.skipped.sort((a, b) => a - b), slope: fitSlope(points) };
    });
}

/** Reads a declared bound like "O(n^2)", "O(n log n)", "O(1)" as a polynomial exponent for the guide line.
 *  Anything else (2^n, n!, ...) returns null: shown as text only, never as a line. n log n is drawn as exponent 1. */
export function declaredExponent(text) {
  if (typeof text !== "string") return null;
  const t = text.replace(/\s+/g, "").toLowerCase();
  if (t === "o(1)") return 0;
  if (t === "o(n)" || t === "o(nlogn)" || t === "o(nlog(n))") return 1;
  const m = t.match(/^o\(n\^(\d+(?:\.\d+)?)\)$/);
  return m ? Number(m[1]) : null;
}

/** Runs grouped by algorithm + commit, newest first. A run with no commit goes in an "unrecorded" group (commit null). */
export function groupRunsByCommit(runs) {
  const map = new Map();
  for (const r of runs) {
    const commit = r.commit || null;
    const key = `${r.algorithmId}\u0000${commit ?? ""}`;
    if (!map.has(key)) map.set(key, { key, algorithmId: r.algorithmId, commit, runs: [], valid: 0, first: r.timestamp, last: r.timestamp });
    const g = map.get(key);
    g.runs.push(r);
    if (r.valid) g.valid += 1;
    if (r.timestamp < g.first) g.first = r.timestamp;
    if (r.timestamp > g.last) g.last = r.timestamp;
  }
  return [...map.values()].sort((a, b) => b.last.localeCompare(a.last) || a.algorithmId.localeCompare(b.algorithmId));
}

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

/** Compare two groups of runs of one algorithm on the instances both ran. A repeated instance uses its latest run.
 *  Failed runs have no visits or distance, so they are left out of those means; failedA/failedB count them. */
export function compareVersions(runsA, runsB) {
  const latest = (runs) => {
    const m = new Map();
    for (const r of runs) {
      const prev = m.get(r.instanceId);
      if (!prev || r.timestamp > prev.timestamp) m.set(r.instanceId, r);
    }
    return m;
  };
  const a = latest(runsA), b = latest(runsB);
  const shared = [...a.keys()].filter((id) => b.has(id)).sort();
  const metric = (key, needValid) => {
    const ids = shared.filter((id) => (!needValid || (a.get(id).valid && b.get(id).valid))
      && has(a.get(id)[key]) && has(b.get(id)[key]));
    const ma = mean(ids.map((id) => a.get(id)[key])), mb = mean(ids.map((id) => b.get(id)[key]));
    return { a: ma, b: mb, delta: ma == null ? null : mb - ma, n: ids.length };
  };
  return {
    sharedInstances: shared.length,
    onlyA: a.size - shared.length, onlyB: b.size - shared.length,
    failedA: shared.filter((id) => !a.get(id).valid).length, failedB: shared.filter((id) => !b.get(id).valid).length,
    visited: metric("visited", true), distanceKm: metric("distanceKm", true), runtimeMs: metric("runtimeMs", false),
  };
}
