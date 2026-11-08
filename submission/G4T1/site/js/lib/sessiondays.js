// Pure logic for the "Until every place is visited" views (no DOM). Tested by tests/test_site_sessiondays.py.
// A session (harness/session.py) is one algorithm on one instance, day by day. Its day records use the ORIGINAL
// place ids, so they draw on the original instance with the same map code as a first-day run.
// A "completed day" has a valid route that visited new places; a stopped session's last day usually is not one.

const completed = (d) => d.valid !== false && Array.isArray(d.route) && d.route.length > 1 && (d.visited || []).length > 0;
const completedDays = (s) => (s?.dayRecords || []).filter(completed);

/** How many days the session completed (what the day selector offers). */
export const dayCount = (s) => completedDays(s).length;

/** Longest session among those shown. */
export const maxDays = (sessions) => Math.max(0, ...sessions.map(dayCount));

/** [{ value: 1, label: "Day 1" }, ...] */
export const dayOptions = (n) => Array.from({ length: n }, (_, i) => ({ value: i + 1, label: `Day ${i + 1}` }));

/** A day number from the URL forced into 1..max (anything unreadable is Day 1). */
export function clampDay(day, max) {
  const n = Math.trunc(Number(day));
  return Number.isFinite(n) && n >= 1 ? Math.min(n, Math.max(1, max)) : 1;
}

const dayRecord = (s, day) => completedDays(s).find((d) => d.day === day) || null;

/** Place ids visited on days before `day`, sorted. */
export function doneBefore(s, day) {
  return completedDays(s).filter((d) => d.day < day).flatMap((d) => d.visited).sort((a, b) => a - b);
}

/** Customer ids not yet visited when `day` starts, sorted. */
export function stillToVisit(instance, s, day) {
  const done = new Set(doneBefore(s, day));
  return instance.locations.filter((l) => !l.isDepot && !done.has(l.id)).map((l) => l.id).sort((a, b) => a - b);
}

/** A day as the map's run input (route and schedule in original ids), or null when the session has no such day. */
export function dayRun(instance, s, day) {
  const d = dayRecord(s, day);
  if (!d) return null;
  return { algorithmId: s.algorithmId, valid: true, route: d.route, schedule: d.schedule, returnMinute: d.returnMinute,
    visited: d.visited.length, distanceKm: d.distanceKm, totalMinutes: d.returnMinute - instance.departureMinute,
    workingMinutes: d.workingMinutes, runtimeMs: d.runtimeMs };
}

/** Why a session has no route for `day`: null when it has one, else plain words. */
export function dayEnding(s, day) {
  const n = dayCount(s);
  if (day <= n) return null;
  if (s.outcome === "finished") return `finished on day ${n}`;
  return n ? `stopped after day ${n}, did not finish` : "stopped before finishing a day, did not finish";
}

const num = (x) => String(Math.round(x * 10) / 10);
const hours = (min) => { const h = Math.round(min / 6) / 10; return `${num(h)} ${h === 1 ? "hour" : "hours"}`; };

/** Plain-words figures for a session. Stopped sessions never show a finishing time: their figures say "so far". */
export function sessionSummary(s) {
  if (s.outcome === "finished") {
    return { finished: true, explanation: null, note: null,
      rows: [["Working time", hours(s.workingMinutes)], ["Days", String(s.days)], ["Distance", `${num(s.totalDistanceKm)} km`]] };
  }
  return { finished: false, explanation: s.explanation, note: "so far, not a finishing time",
    rows: [["Days completed", String(dayCount(s))], ["Places visited so far", `${s.visitedSoFar} of ${s.numCustomers}`],
      ["Working time so far", hours(s.workingMinutes)], ["Distance so far", `${num(s.totalDistanceKm)} km`]] };
}

/** Newest session of each algorithm on one problem, in algorithm order. */
export function latestPerAlgorithm(entries, instanceId) {
  const best = new Map();
  for (const e of entries.filter((x) => x.instanceId === instanceId)) {
    const old = best.get(e.algorithmId);
    if (!old || (e.timestamp || "") >= (old.timestamp || "")) best.set(e.algorithmId, e);
  }
  return [...best.values()].sort((a, b) => a.algorithmId.localeCompare(b.algorithmId));
}

/** Problems that have a session, smallest first. */
export function sessionInstanceIds(entries) {
  const seen = new Map(entries.map((e) => [e.instanceId, e]));
  return [...seen.values()].sort((a, b) => a.numCustomers - b.numCustomers || a.seed - b.seed).map((e) => e.instanceId);
}
