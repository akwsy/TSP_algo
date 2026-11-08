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

/** A range of a swept setting with the unit said once: "5 to 100 places", "speed 20 to 80 km/h". */
export function sweepRange(param, lo, hi) {
  if (!has(lo) || !has(hi) || lo === hi) return sweepLabel(param, has(lo) ? lo : hi);
  switch (param) {
    case "customers": return `${lo} to ${plural(hi, "place")}`;
    case "period": return `day length ${hours(lo)} to ${hours(hi)}`;
    case "speed": return `speed ${lo} to ${hi} km/h`;
    case "departure": return `leaves at ${clock(lo)} to ${clock(hi)}`;
    case "radius": return `customers within ${lo} to ${hi} km`;
    default: return `${param} ${lo} to ${hi}`;
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

// ---- experiment cards ----

const QUESTIONS = {
  scaling: "What happens as there are more places to visit?",
  "time-budget": "What happens when the working day is shorter or longer?",
  speed: "What happens when travel is slower or faster?",
  "window-alignment": "Does it matter what time of day the trip starts?",
  spread: "What happens when the places are closer together or further apart?",
  stress: "Do they keep up with very many places?",
};
/** The question an experiment answers, in plain words (its description for an experiment this page does not know). */
export const experimentQuestion = (e) => QUESTIONS[e?.name] || e?.description || "How do the algorithms compare here?";

// Fixed parameters as written in aggregates `parameters`, with the sweep parameter each one corresponds to.
const FIXED = [["customers", "customers"], ["departureMinute", "departure"], ["periodMinutes", "period"], ["speedKmh", "speed"], ["radiusKm", "radius"]];

/** "Changes: day length 4 h to 18 h. Fixed: 30 places, leaves at 06:00, ... 30 examples per setting." */
export function settingsText(e) {
  const p = e.agg?.parameters || {};
  const v = e.values;
  const changes = v.length ? `Changes: ${sweepRange(e.param, v[0], v[v.length - 1])}.` : "";
  const fixed = FIXED.filter(([key, param]) => param !== e.param && has(p[key])).map(([key, param]) => sweepLabel(param, p[key]));
  const per = has(e.instancesPerSize) ? `${plural(e.instancesPerSize, "example")} per setting.` : "";
  return [changes, fixed.length ? `Fixed: ${fixed.join(", ")}.` : "", per].filter(Boolean).join(" ");
}

/** Chart series for one measure: one per algorithm (sorted by id), points by sweep value with mean +/- one standard
 *  deviation as the band (null when there is no deviation). Missing means are left out, never drawn as 0. */
export function experimentSeries(e, metric) {
  const byAlg = new Map();
  for (const g of e.agg.groups) {
    const s = g[metric];
    if (!s || !has(s.mean) || !has(g.sweepValue)) continue;
    const std = has(s.std) ? s.std : null;
    if (!byAlg.has(g.algorithmId)) byAlg.set(g.algorithmId, []);
    byAlg.get(g.algorithmId).push({ x: g.sweepValue, y: s.mean, lo: std == null ? null : s.mean - std, hi: std == null ? null : s.mean + std });
  }
  return [...byAlg].sort((a, b) => a[0].localeCompare(b[0])).map(([algorithmId, points]) => ({ algorithmId, points: points.sort((a, b) => a.x - b.x) }));
}

/** One line on what an experiment shows: who visits the most places at how many settings, and how its lead over the
 *  next best changes from the first to the last setting. */
export function experimentTakeaway(e, names = {}) {
  const nm = (id) => names[id] || id;
  const model = { experiments: [e], algorithms: [...new Set(e.agg.groups.map((g) => g.algorithmId))].sort() };
  const leader = standings(model).overall[0];
  if (!leader || !has(standings(model).byExperiment[0].ranking[0]?.mean)) return "No valid results to compare.";
  const tops = new Map();
  let level = 0, close = 0;
  const leads = [];
  for (const value of e.values) {
    const here = e.agg.groups.filter((g) => g.sweepValue === value && has(g.visited?.mean)).sort((x, y) => y.visited.mean - x.visited.mean);
    if (!here.length) continue;
    if (here.length > 1 && Math.abs(here[0].visited.mean - here[1].visited.mean) < 1e-9) level += here[0].algorithmId === leader.id || here[1].algorithmId === leader.id ? 1 : 0;
    else {
      tops.set(here[0].algorithmId, (tops.get(here[0].algorithmId) || 0) + 1);
      if (here[0].algorithmId === leader.id && here.length > 1 && pairCell(e.agg, value, leader.id, here[1].algorithmId)?.verdict === "even") close += 1;
    }
    const mine = here.find((g) => g.algorithmId === leader.id), best = here.find((g) => g.algorithmId !== leader.id);
    if (mine && best) leads.push({ value, lead: mine.visited.mean - best.visited.mean });
  }
  const total = e.values.length, n = tops.get(leader.id) || 0;
  let text = `${nm(leader.id)} visits the most places on average at ${n === total ? `all ${plural(total, "setting")}` : `${n} of ${plural(total, "setting")}`}`;
  if (close) text += `, ${close} of them within the margin of error`;
  if (level) text += ` and is level at ${level}`;
  const others = [...tops].filter(([id]) => id !== leader.id).map(([id, k]) => `${nm(id)} at ${k}`);
  if (others.length) text += `; ${others.join(", ")}`;
  const word = (x) => (Math.abs(x) < 1e-9 ? "none" : x > 0 ? diffNum(x) : `${diffNum(x)} behind`);
  if (leads.length > 1) {
    const [f, l] = [leads[0], leads[leads.length - 1]];
    text += `; its lead over the next best goes from ${word(f.lead)} (${sweepLabel(e.param, f.value)}) to ${word(l.lead)} (${sweepLabel(e.param, l.value)})`;
  } else if (leads.length) text += `; its lead over the next best is ${word(leads[0].lead)}`;
  return `${text}.`;
}

// ---- algorithm profiles ----

/** A run time in ms as people read it: "4.2 ms", "166 ms", "2.3 s". */
export function msText(x) {
  if (!has(x)) return "n/a";
  if (x >= 1000) return `${num(x / 1000, 1)} s`;
  return `${num(x, x < 10 ? 1 : 0)} ms`;
}
const msRange = (lo, hi) => {
  const a = msText(lo), b = msText(hi);
  return a.endsWith(" ms") && b.endsWith(" ms") ? `${a.slice(0, -3)} to ${b}` : `${a} to ${b}`;
};
const median = (xs) => {
  const v = xs.filter(has).sort((a, b) => a - b);
  if (!v.length) return null;
  const k = Math.floor(v.length / 2);
  return v.length % 2 ? v[k] : (v[k - 1] + v[k]) / 2;
};

/** Measured facts per algorithm (in model.algorithms order): average rank across experiments, head-to-head examples
 *  won/tied/lost against all others, typical (median over settings) run time and its range, the average share of the
 *  best known result, and the setting with its biggest lead (strongest) and biggest deficit (weakest), where
 *  margin = its average places visited minus the best of the others there (rival = that best other). */
export function profiles(model) {
  const { overall } = standings(model);
  return model.algorithms.map((id) => {
    const h2h = { won: 0, tied: 0, lost: 0, total: 0 };
    const times = [], shares = [];
    let strongest = null, weakest = null;
    for (const { e, value } of settings(model)) {
      for (const p of e.agg.pairs || []) {
        if (p.sweepValue !== value || (p.a !== id && p.b !== id)) continue;
        const mine = p.a === id ? p.aWins : p.bWins, theirs = p.a === id ? p.bWins : p.aWins;
        h2h.won += has(mine) ? mine : 0; h2h.lost += has(theirs) ? theirs : 0; h2h.tied += has(p.ties) ? p.ties : 0;
      }
      const here = e.agg.groups.filter((g) => g.sweepValue === value);
      const g = here.find((x) => x.algorithmId === id);
      if (!g) continue;
      times.push(g.runtimeMs?.mean); shares.push(g.bestKnownRatio?.mean);
      const others = here.filter((x) => x.algorithmId !== id && has(x.visited?.mean));
      if (!has(g.visited?.mean) || !others.length) continue;
      const rival = others.reduce((b, x) => (x.visited.mean > b.visited.mean ? x : b));
      const spot = { experiment: e.name, param: e.param, value, rival: rival.algorithmId, margin: g.visited.mean - rival.visited.mean };
      if (!strongest || spot.margin > strongest.margin) strongest = spot;
      if (!weakest || spot.margin < weakest.margin) weakest = spot;
    }
    h2h.total = h2h.won + h2h.tied + h2h.lost;
    const o = overall.find((x) => x.id === id);
    const tv = times.filter(has);
    return { id, avgRank: o?.avgRank ?? null, experiments: o?.experiments ?? 0, h2h,
      runtime: { typical: median(tv), low: tv.length ? Math.min(...tv) : null, high: tv.length ? Math.max(...tv) : null },
      bestShare: mean(shares), strongest, weakest };
  });
}

/** How one setting compares with the best other algorithm there, in words. */
function spotText(spot, names) {
  if (!spot) return "n/a";
  const rival = names[spot.rival] || spot.rival;
  const at = `at ${sweepLabel(spot.param, spot.value)} (${experimentTitle(spot.experiment)})`;
  if (Math.abs(spot.margin) < 1e-9) return `level with ${rival} ${at}`;
  return `${diffNum(spot.margin)} ${spot.margin < 0 ? "fewer" : "more"} places than ${rival} ${at}`;
}

/** The profile as [label, text] rows for the profile card. */
export function profileFacts(p, names = {}) {
  const share = (x) => `${Math.round((x / p.h2h.total) * 100)}%`;
  return [
    ["Average rank", has(p.avgRank) ? `${num(p.avgRank, 1)} across ${plural(p.experiments, "experiment")}` : "n/a"],
    ["Head to head", p.h2h.total ? `won ${share(p.h2h.won)}, tied ${share(p.h2h.tied)}, lost ${share(p.h2h.lost)} of ${plural(p.h2h.total, "example")}` : "no examples compared"],
    ["Typical run time", has(p.runtime.typical) ? `${msText(p.runtime.typical)} (${msRange(p.runtime.low, p.runtime.high)} across settings)` : "n/a"],
    ["Share of the best found", has(p.bestShare) ? `${num(p.bestShare * 100, 1)}% of the most places any algorithm reached, on average` : "n/a"],
    ["Strongest", spotText(p.strongest, names)],
    ["Weakest", spotText(p.weakest, names)],
  ];
}

// ---- trade-off: run time against places visited ----

const dominates = (o, p) => o.runtimeMs <= p.runtimeMs && o.visited >= p.visited && (o.runtimeMs < p.runtimeMs || o.visited > p.visited);

/** One point per algorithm (model.algorithms order): average run time and average places visited at one setting
 *  (experiment name and sweep value), or over every setting of every experiment when `experiment` is null (each
 *  setting weighs the same). frontier: true when no other algorithm is at least as fast and visits at least as many
 *  places (better in one), false when one is, null when the point has a missing value. */
export function tradeoff(model, experiment, value) {
  const groups = model.experiments.filter((e) => experiment == null || e.name === experiment)
    .flatMap((e) => e.agg.groups.filter((g) => experiment == null || g.sweepValue === value));
  const points = model.algorithms.map((id) => {
    const mine = groups.filter((g) => g.algorithmId === id);
    return { id, runtimeMs: mean(mine.map((g) => g.runtimeMs?.mean)), visited: mean(mine.map((g) => g.visited?.mean)), settings: mine.length };
  }).filter((p) => p.settings > 0);
  const ok = (p) => has(p.runtimeMs) && has(p.visited);
  for (const p of points) {
    p.frontier = ok(p) ? !points.some((o) => o !== p && ok(o) && dominates(o, p)) : null;
    p.dominatedBy = p.frontier === false ? points.filter((o) => o !== p && ok(o) && dominates(o, p)).sort((x, y) => x.runtimeMs - y.runtimeMs)[0].id : null;
  }
  return points;
}

/** The frontier in words: who is on it, who is not and why, and who cannot be placed. */
export function frontierText(points, names = {}) {
  const nm = (id) => names[id] || id;
  const on = points.filter((p) => p.frontier === true).sort((x, y) => x.runtimeMs - y.runtimeMs);
  const out = [];
  if (on.length) out.push(`On the efficient frontier (nothing else is both faster and visits more places): ${on.map((p) => nm(p.id)).join(", ")}${on.length > 1 ? ", from fastest to most places" : ""}.`);
  for (const p of points.filter((x) => x.frontier === false)) {
    const o = points.find((x) => x.id === p.dominatedBy);
    out.push(`${nm(p.id)} is off the frontier: ${nm(o.id)} is ${o.runtimeMs < p.runtimeMs ? "faster" : "as fast"} and visits ${o.visited > p.visited ? "more" : "as many"} places.`);
  }
  for (const p of points.filter((x) => x.frontier === null)) {
    out.push(`${nm(p.id)} has no ${has(p.runtimeMs) ? "places-visited average" : "run time"}, so it cannot be placed.`);
  }
  return out;
}

// ---- where they differ ----

/** For every pair of algorithms (a before b alphabetically), the examples with the biggest gap in places visited in
 *  each direction across all experiments: aAhead (a visited more) and bAhead, at most `perSide` each, biggest first
 *  (ties in suite and sweep order). An example listed at several settings (a shared default) is kept once.
 *  Only the largest gaps of each setting are in the files, so smaller ones can be missing. */
export function pairGaps(model, perSide = 3) {
  const out = new Map();
  model.experiments.forEach((e, ei) => {
    e.values.forEach((value, vi) => {
      for (const p of e.agg.pairs || []) {
        if (p.sweepValue !== value) continue;
        const key = `${p.a}\u0000${p.b}`;
        if (!out.has(key)) out.set(key, { a: p.a, b: p.b, rows: [], seen: new Set() });
        const entry = out.get(key);
        for (const g of p.largestGaps || []) {
          if (!has(g.difference) || g.difference === 0 || entry.seen.has(g.instanceId)) continue;
          entry.seen.add(g.instanceId);
          entry.rows.push({ experiment: e.name, param: e.param, value, instanceId: g.instanceId,
            aVisited: g.aVisited, bVisited: g.bVisited, difference: g.difference, order: [ei, vi] });
        }
      }
    });
  });
  const pick = (rows) => rows.sort((x, y) => Math.abs(y.difference) - Math.abs(x.difference) || x.order[0] - y.order[0] || x.order[1] - y.order[1]
    || x.instanceId.localeCompare(y.instanceId)).slice(0, perSide).map(({ order, ...r }) => r);
  return [...out.values()].sort((x, y) => x.a.localeCompare(y.a) || x.b.localeCompare(y.b))
    .map(({ a, b, rows }) => ({ a, b, aAhead: pick(rows.filter((r) => r.difference > 0)), bAhead: pick(rows.filter((r) => r.difference < 0)) }));
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
