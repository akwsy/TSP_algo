// Listing logic for full-run sessions on the Failures and History pages (no DOM except loadSessions).
// Data: results/sessions-index.json ({ sessions: [...] }, see harness/sessionstore.py); its entries carry every
// figure listed here, so session files (harness/session.py) are fetched only for entries from an older index. A missing index means no sessions. Tested by tests/test_site_sessions.py.
// Stopped sessions are never turned into a finishing time: their figures are labelled "so far".
import { failureKind } from "./model.js";
import { loadSession, loadSessionsIndex } from "./data.js";

export const STOPPED_KIND = "did not finish every place";
const has = (x) => typeof x === "number" && Number.isFinite(x);
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const round1 = (x) => Math.round(x * 10) / 10;

/** Sessions from a parsed sessions-index.json; empty when the file is absent or malformed. */
export const sessionsOf = (idx) => (Array.isArray(idx?.sessions) ? idx.sessions : []);

export const isStopped = (s) => s.outcome === "did not finish";

export const exampleWords = (s) => `Example ${s.seed} with ${plural(s.numCustomers, "place")}`;

export const hoursOf = (minutes) => (has(minutes) ? minutes / 60 : null);

/** "3 of 5 places visited so far, 2.5 working hours so far (so far, not a finishing time)" */
export function partialText(s) {
  const hrs = hoursOf(s.workingMinutes);
  return `${s.visitedSoFar} of ${plural(s.numCustomers, "place")} visited so far, ${hrs == null ? "no" : round1(hrs)} working hours so far (so far, not a finishing time)`;
}

/** One list for the Failures page: failed first-day runs plus stopped sessions, newest first. */
export function mergeFailures(runs, sessions) {
  const items = [
    ...runs.map((r) => ({ type: "run", kind: failureKind(r), algorithmId: r.algorithmId, timestamp: r.timestamp || "", run: r })),
    ...sessions.filter(isStopped).map((s) => ({ type: "session", kind: STOPPED_KIND, algorithmId: s.algorithmId, timestamp: s.timestamp || "", session: s })),
  ];
  return items.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
}

export const kindsOf = (items) => ["all", ...[...new Set(items.map((i) => i.kind))].sort()];
export const algorithmsOf = (items) => ["all", ...new Set(items.map((i) => i.algorithmId))];
export const filterItems = (items, kind, alg) =>
  items.filter((i) => (kind === "all" || i.kind === kind) && (alg === "all" || i.algorithmId === alg));

/** Sessions grouped like groupRunsByCommit (same key shape), newest first, each saved file once.
 *  Each session needs `commit` (from its session file; absent means "no commit recorded"). */
export function groupSessionsByVersion(sessions) {
  const map = new Map();
  const seen = new Set();
  for (const s of sessions) {
    if (seen.has(s.file)) continue;
    seen.add(s.file);
    const commit = s.commit || null;
    const key = `${s.algorithmId}\u0000${commit ?? ""}`;
    if (!map.has(key)) map.set(key, { key, algorithmId: s.algorithmId, commit, sessions: [], finished: 0, first: s.timestamp, last: s.timestamp });
    const g = map.get(key);
    g.sessions.push(s);
    if (!isStopped(s)) g.finished += 1;
    if (s.timestamp < g.first) g.first = s.timestamp;
    if (s.timestamp > g.last) g.last = s.timestamp;
  }
  return [...map.values()].sort((a, b) => b.last.localeCompare(a.last) || a.algorithmId.localeCompare(b.algorithmId));
}

/** Before/after for two versions' sessions, over examples both versions ran. Means (working hours, days, distance)
 *  use only examples both finished; stopped sessions are counted, never averaged. A repeated example uses its latest. */
export function compareFull(sa, sb) {
  const latest = (list) => {
    const m = new Map();
    for (const s of list) {
      const p = m.get(s.instanceId);
      if (!p || s.timestamp > p.timestamp) m.set(s.instanceId, s);
    }
    return m;
  };
  const a = latest(sa), b = latest(sb);
  const shared = [...a.keys()].filter((id) => b.has(id)).sort();
  const both = shared.filter((id) => !isStopped(a.get(id)) && !isStopped(b.get(id)));
  const metric = (get) => {
    const ids = both.filter((id) => has(get(a.get(id))) && has(get(b.get(id))));
    const ma = mean(ids.map((id) => get(a.get(id)))), mb = mean(ids.map((id) => get(b.get(id))));
    return { a: ma, b: mb, delta: ma == null ? null : mb - ma, n: ids.length };
  };
  return {
    shared: shared.length, both: both.length,
    finishedA: shared.filter((id) => !isStopped(a.get(id))).length,
    finishedB: shared.filter((id) => !isStopped(b.get(id))).length,
    hours: metric((s) => hoursOf(s.workingMinutes)), days: metric((s) => s.days),
    distanceKm: metric((s) => s.totalDistanceKm),
  };
}

// ---- browser loading ----
let cached = null;
const DETAIL_FIELDS = ["commit", "totalDistanceKm", "explanation"];

/** True when an index entry already carries what the pages list (older indexes do not). */
export const hasDetails = (e) => DETAIL_FIELDS.every((k) => k in e);

/** Sessions for the Failures and History pages, read from sessions-index.json alone (its entries carry commit,
 *  totalDistanceKm and explanation, see harness/sessionstore.py). Only an entry from an older index that lacks them
 *  is completed from its session file. Cached. Never throws: no index or an unreadable file means fewer details. */
export function loadSessions() {
  if (!cached) {
    cached = loadSessionsIndex().then((entries) => Promise.all(entries.map(async (e) => {
      if (hasDetails(e)) return e;
      try {
        const rec = await loadSession(e.file);
        return { ...e, commit: rec.commit ?? null, totalDistanceKm: rec.totalDistanceKm, explanation: rec.explanation };
      } catch { return e; }
    })));
  }
  return cached;
}
