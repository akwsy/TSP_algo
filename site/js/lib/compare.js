// Pure logic for the Compare page (no DOM): reads results/suite.json and the aggregates-<name>.json files of an
// experiment series and turns them into plain-words facts. Tested by tests/test_site_compare.py.
// Every number can be missing (null) in the files: such values are shown as "n/a" and left out of averages, never 0.

const has = (x) => typeof x === "number" && Number.isFinite(x);

/** "1 place", "3 places"; `word` is the singular, `many` the plural when it is not word + "s". */
export function plural(n, word, many = `${word}s`) {
  return `${has(n) ? n.toLocaleString("en") : "n/a"} ${n === 1 ? word : many}`;
}

/** A number with fixed decimals, or "n/a". */
export const num = (x, digits = 1) =>
  has(x) ? x.toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "n/a";

const clock = (minute) => `${String(Math.floor(minute / 60) % 24).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
const hours = (minutes) => `${+(minutes / 60).toFixed(2)} h`;

/** The value of a swept setting in everyday words: "30 places", "day length 8 h", "speed 40 km/h", "leaves at 09:00",
 *  "customers within 50 km". */
export function sweepLabel(param, value) {
  if (!has(value)) return `${param} n/a`;
  switch (param) {
    case "customers": return plural(value, "place");
    case "period": return `day length ${hours(value)}`;
    case "speed": return `speed ${value} km/h`;
    case "departure": return `leaves at ${clock(value)}`;
    case "radius": return `customers within ${value} km`;
    default: return `${param} ${value}`;
  }
}

/** The experiment series: experiments in suite order that have their aggregates (`aggs` maps name to the parsed
 *  file, or null when it could not be loaded), the names of those without, and every algorithm id, sorted. */
export function buildModel(suite, aggs) {
  const listed = Array.isArray(suite?.experiments) ? suite.experiments : [];
  const experiments = [], missing = [];
  for (const e of listed) {
    const agg = aggs?.[e.name];
    if (!agg || !Array.isArray(agg.groups)) { missing.push(e.name); continue; }
    const values = (Array.isArray(agg.sweepValues) ? agg.sweepValues : e.values || []).filter(has);
    experiments.push({ name: e.name, description: e.description || "", param: agg.parameters?.sweepParam || e.param,
      values, instancesPerSize: agg.parameters?.instancesPerSize ?? e.instancesPerSize ?? null, agg });
  }
  const algorithms = [...new Set(experiments.flatMap((e) => e.agg.groups.map((g) => g.algorithmId)))].sort();
  return { experiments, missing, algorithms };
}

const TITLES = { scaling: "Number of places", "time-budget": "Day length", speed: "Travel speed", "window-alignment": "Departure time",
  spread: "How spread out", stress: "Very many places" };
/** A short plain-words title for an experiment ("time-budget" is "Day length"); unknown names are tidied up. */
export function experimentTitle(name) {
  if (TITLES[name]) return TITLES[name];
  const t = String(name ?? "").replace(/[-_]+/g, " ").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : "Experiment";
}

const mean = (xs) => { const v = xs.filter(has); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };

/** Every (experiment, sweep value) of the model, in order. */
const settings = (model) => model.experiments.flatMap((e) => e.values.map((value) => ({ e, value })));

/** Ranking per experiment by average places visited over its sweep values (equal averages share a rank, missing
 *  averages come last without a rank), and overall: average rank and how many experiments each algorithm led
 *  (`firsts`), best first. */
export function standings(model) {
  const byExperiment = model.experiments.map((e) => {
    const rows = model.algorithms.map((id) => ({ id,
      mean: mean(e.agg.groups.filter((g) => g.algorithmId === id).map((g) => g.visited?.mean)) }))
      .filter((r) => e.agg.groups.some((g) => g.algorithmId === r.id));
    rows.sort((x, y) => (has(y.mean) - has(x.mean)) || (has(x.mean) ? y.mean - x.mean : 0) || x.id.localeCompare(y.id));
    for (const r of rows) r.rank = has(r.mean) ? 1 + rows.filter((o) => has(o.mean) && o.mean > r.mean).length : null;
    return { name: e.name, ranking: rows };
  });
  const overall = model.algorithms.map((id) => {
    const ranks = byExperiment.map((x) => x.ranking.find((r) => r.id === id)?.rank);
    return { id, avgRank: mean(ranks), firsts: ranks.filter((r) => r === 1).length, experiments: ranks.filter(has).length };
  }).sort((x, y) => y.firsts - x.firsts || (x.avgRank ?? Infinity) - (y.avgRank ?? Infinity) || x.id.localeCompare(y.id));
  return { byExperiment, overall };
}

const ORD = (n) => `${n}${n % 10 === 1 && n % 100 !== 11 ? "st" : n % 10 === 2 && n % 100 !== 12 ? "nd" : n % 10 === 3 && n % 100 !== 13 ? "rd" : "th"}`;

/** The mean over every setting of `row` minus `col` in places visited (null when never compared). */
function meanLead(model, row, col) {
  return mean(settings(model).map(({ e, value }) => pairCell(e.agg, value, row, col)?.diff));
}

/** The headline: who visits the most places in how many experiments and by how much, everyone's standing, and caveats
 *  computed from the data. `names` maps id to display name; `algs` is the declared metadata (for "exact"). */
export function headline(model, names = {}, algs = {}) {
  const nm = (id) => names[id] || id;
  if (!model.experiments.length) return { leader: null, text: "No experiment results yet.", standing: [], caveats: [] };
  const { overall } = standings(model);
  const total = model.experiments.length, nSettings = settings(model).length;
  const [first, second] = overall;
  const where = first.firsts === total ? (total === 1 ? "the one experiment" : `all ${total} experiments`) : `${first.firsts} of ${plural(total, "experiment")}`;
  const leads = overall.slice(1).map((o) => ({ id: o.id, d: meanLead(model, first.id, o.id) })).filter((x) => has(x.d));
  const leadText = leads.map((x, i) => `${diffNum(x.d)} ${x.d < 0 ? "fewer" : "more"}${i ? "" : " places"} than ${nm(x.id)}`);
  const joined = leadText.length > 1 ? `${leadText.slice(0, -1).join(", ")} and ${leadText[leadText.length - 1]}` : leadText[0];
  const level = second && second.firsts === first.firsts && second.avgRank === first.avgRank;
  const text = level
    ? `${nm(first.id)} and ${nm(second.id)} visited the most places equally often (each first in ${first.firsts} of ${plural(total, "experiment")}), over ${plural(nSettings, "setting")}.`
    : `${nm(first.id)} visited the most places in ${where}${joined ? `: on average ${joined}` : ""}, over ${plural(nSettings, "setting")}.`;
  const standing = overall.map((o, i) => `${ORD(i + 1)} ${nm(o.id)}, average rank ${num(o.avgRank, 1)}`);

  const caveats = [];
  const groups = model.experiments.flatMap((e) => e.agg.groups);
  const runs = groups.reduce((n, g) => n + (has(g.runs) ? g.runs : 0), 0);
  const tally = (key) => {
    const per = model.algorithms.map((id) => [id, groups.filter((g) => g.algorithmId === id).reduce((n, g) => n + (has(g[key]) ? g[key] : 0), 0)]).filter(([, n]) => n > 0);
    return { n: per.reduce((s, [, n]) => s + n, 0), who: per.map(([id, n]) => `${nm(id)} ${n}`).join(", ") };
  };
  const f = tally("failures"), t = tally("timeouts");
  if (!f.n && !t.n) caveats.push(`No failures or timeouts in ${plural(runs, "run")}.`);
  else {
    const parts = [];
    if (f.n) parts.push(`${f.n} of ${plural(runs, "run")} failed (${f.who})`);
    if (t.n) parts.push(`${parts.length ? "" : `of ${plural(runs, "run")}, `}${t.n} hit the time limit (${t.who})`);
    caveats.push(`${parts.join(" and ")}; they are left out of the averages.`);
  }
  if (second && !level) {
    const close = model.experiments.map((e) => {
      const cells = e.values.map((v) => pairCell(e.agg, v, first.id, second.id)).filter(Boolean);
      return { e, n: cells.filter((c) => c.verdict === "even").length, of: cells.length };
    });
    const nClose = close.reduce((s, c) => s + c.n, 0), nOf = close.reduce((s, c) => s + c.of, 0);
    const list = close.filter((c) => c.n > 0).sort((x, y) => y.n - x.n)
      .map((c) => `${experimentTitle(c.e.name)} (${c.n} of ${c.of})`).join(", ");
    if (nClose) caveats.push(`${nm(first.id)} and ${nm(second.id)} are within the margin of error of each other at ${nClose} of ${plural(nOf, "setting")}: ${list}.`);
    else if (nOf) caveats.push(`${nm(first.id)} is ahead of ${nm(second.id)} beyond the margin of error at every one of ${plural(nOf, "setting")}.`);
  }
  const excluded = model.experiments.flatMap((e) => e.agg.pairs || []).reduce((n, p) => n + (has(p.excluded) ? p.excluded : 0), 0);
  if (excluded) caveats.push(`${plural(excluded, "example")} ${excluded === 1 ? "was" : "were"} left out of head-to-head comparisons because a run gave no valid answer.`);
  const meta = model.algorithms.map((id) => algs[id]).filter(Boolean);
  if (meta.length === model.algorithms.length && meta.length && meta.every((a) => a.exact === false)) {
    caveats.push("None of the algorithms is exact, so \"best\" means the best any of them found, not the best possible.");
  }
  return { leader: first.id, text, standing, caveats };
}

// ---- head to head ----

/** A difference with one decimal, two when it is small but not zero (so 0.03 never reads as 0.0). */
const diffNum = (x) => num(Math.abs(x), Math.abs(x) > 0 && Math.abs(x) < 0.1 ? 2 : 1);
const sameSign = (x, y) => (x > 0 && y > 0) || (x < 0 && y < 0);

/** The verdict on a difference in places visited from its margin of error: "more" or "fewer" when the whole margin
 *  lies on one side of zero, "even" when it includes zero, null when nothing was compared. */
export function verdict(ci) {
  if (!Array.isArray(ci) || !has(ci[0]) || !has(ci[1])) return null;
  return ci[0] > 0 ? "more" : ci[1] < 0 ? "fewer" : "even";
}

/** One cell of the head-to-head grid: `row` against `col` at one sweep value, read from the row's side
 *  (wins are the row's wins, diff is row minus col). null when the file has no such pair. */
export function pairCell(agg, value, row, col) {
  const [a, b] = [row, col].sort();
  const p = (agg?.pairs || []).find((q) => q.sweepValue === value && q.a === a && q.b === b);
  if (!p || row === col) return null;
  const flip = row !== p.a;
  const sign = (x) => (has(x) ? (flip ? -x : x) : null);
  const ci = Array.isArray(p.visitDiffCI95) && has(p.visitDiffCI95[0]) && has(p.visitDiffCI95[1])
    ? (flip ? [-p.visitDiffCI95[1], -p.visitDiffCI95[0]] : [p.visitDiffCI95[0], p.visitDiffCI95[1]]) : null;
  return {
    row, col, sweepParam: p.sweepParam, sweepValue: p.sweepValue,
    wins: flip ? p.bWins : p.aWins, losses: flip ? p.aWins : p.bWins, ties: p.ties,
    examples: p.instances, excluded: p.excluded || 0,
    diff: sign(p.meanVisitDiff), ci, verdict: verdict(ci),
    distanceDiff: sign(p.meanDistanceDiffWhenEqualVisits), overlap: has(p.meanOverlap) ? p.meanOverlap : null,
    gaps: (p.largestGaps || []).map((g) => ({ instanceId: g.instanceId,
      rowVisited: flip ? g.bVisited : g.aVisited, colVisited: flip ? g.aVisited : g.bVisited, difference: sign(g.difference) })),
  };
}

const count = (n) => (n === 0 ? "none" : has(n) ? String(n) : "n/a");
const pct = (x) => (has(x) ? `${Math.round(x * 100)}%` : "n/a");

/** The cell in sentences, row first. `names` maps id to display name. */
export function pairSummary(cell, names = {}) {
  if (!cell) return [];
  const A = names[cell.row] || cell.row, B = names[cell.col] || cell.col;
  const out = [];
  const left = cell.excluded > 0
    ? `${plural(cell.excluded, "example")} ${cell.excluded === 1 ? "was" : "were"} left out because one of them gave no valid answer.` : null;
  if (!(cell.examples > 0) || !has(cell.diff)) {
    out.push(`${A} and ${B} have no example where both gave a valid answer, so they cannot be compared here.`);
    if (left) out.push(left);
    return out;
  }
  const [lo, hi] = cell.ci || [null, null];
  if (cell.diff === 0 && lo === 0 && hi === 0) out.push(`${A} and ${B} visited the same number of places in every example.`);
  else {
    const dir = (x) => (x < 0 ? "fewer" : "more");
    const head = cell.diff === 0 ? `${A} visited on average the same number of places as ${B}`
      : `${A} visited on average ${diffNum(cell.diff)} ${dir(cell.diff)} places than ${B}`;
    const margin = !cell.ci ? "margin of error n/a"
      : sameSign(lo, hi) ? `margin of error ${diffNum(cell.diff < 0 ? hi : lo)} to ${diffNum(cell.diff < 0 ? lo : hi)}`
        : `margin of error from ${diffNum(lo)} ${dir(lo)} to ${diffNum(hi)} ${dir(hi)}, so the difference may be chance`;
    out.push(`${head}, ${margin}.`);
  }
  out.push(`${A} won ${cell.wins} of ${plural(cell.examples, "example")}, tied ${count(cell.ties)} and lost ${count(cell.losses)}.`);
  if (left) out.push(left);
  if (has(cell.distanceDiff)) {
    const d = Math.abs(cell.distanceDiff) < 0.05 ? "the same distance" : `${num(Math.abs(cell.distanceDiff), 1)} km ${cell.distanceDiff < 0 ? "less" : "more"}`;
    out.push(`When both visited the same number of places, ${A} drove on average ${d}.`);
  }
  out.push(cell.overlap == null ? "Their overlap in places visited is n/a." : `Their routes share ${pct(cell.overlap)} of the same places.`);
  return out;
}
