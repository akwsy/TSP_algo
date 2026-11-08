// Pure logic for the "Until every place is visited" views (no DOM). Tested by tests/test_site_view.py.
// Data comes from aggregates-<experiment>.json -> `full` (see harness/aggregate.py aggregate_sessions).
// Working hours are in HOURS there. Stopped instances are never turned into hours.

const REASON_WORDS = {
  no_progress: "stopped visiting new places",
  day_limit: "still not done after 30 days",
  crashed: "crashed",
  invalid_route: "gave an invalid route",
  unreadable_output: "gave an answer that could not be read",
  timed_out: "ran out of time",
  could_not_start: "could not be started",
};

/** "2 crashed, 1 ran out of time" from { crashed: 2, timed_out: 1 }; "" when nothing stopped. */
export function reasonCountsText(reasons) {
  return Object.entries(reasons || {})
    .map(([code, n]) => `${n} ${REASON_WORDS[code] || "stopped for another reason"}`).join(", ");
}

export const rankedBelowText = (n) =>
  n > 0 ? `ranked below: ${n} instance${n === 1 ? "" : "s"} did not finish` : null;

export const finishedText = (finished, total) => `${finished} of ${total}`;

/** True when the results hold a full-run ranking. */
export const hasFull = (agg) => Array.isArray(agg?.full?.ranking) && agg.full.ranking.length > 0;

/** Ranked rows for one size, in display order (finished-everything first), with the extras the table shows. */
export function fullRows(full, size) {
  const block = (full?.ranking || []).find((r) => r.numCustomers === size);
  if (!block) return [];
  return block.entries.map((e) => {
    const g = (full.groups || []).find((x) => x.algorithmId === e.algorithmId && x.numCustomers === size);
    return { ...e, instances: block.instances, rankedBelow: e.unfinished, days: g?.days || null,
             reasons: reasonCountsText(g?.stopReasons) };
  });
}

/** Headline strip figures from the rows of one size. */
export function fullHeadline(rows) {
  const lead = rows.find((r) => r.rank === 1);
  return {
    leaderId: lead ? lead.algorithmId : null,
    compared: rows.length,
    finishedEverything: rows.filter((r) => r.finishedAll).length,
    notFinished: rows.reduce((n, r) => n + r.unfinished, 0),
  };
}
