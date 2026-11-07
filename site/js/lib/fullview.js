// Small DOM pieces shared by the Instance explorer and Route detail in the "Until every place is visited" view.
// The decisions (which days exist, what is done, what the words say) live in sessions.js; this only lays them out.
import { h, fmt, select } from "./dom.js";
import { dayOptions, dayEnding, sessionSummary } from "./sessions.js";
import { clock } from "./mapmodel.js";

/** The day dropdown: a native select named "Day" ("Day 1", "Day 2", ...), so the keyboard and screen readers just work. */
export function daySelect(max, day, onchange) {
  return select("Day", dayOptions(max), day, (v) => onchange(Number(v)));
}

/** Plain-words figures for a whole session, with the stopped explanation when it did not finish. */
export function sessionBlock(session) {
  const s = sessionSummary(session);
  return h("div", { class: "session-summary" },
    s.finished ? null : h("p", { class: "fail-reason" }, h("span", { class: "badge bad" }, "did not finish"), " ", s.explanation),
    h("dl", { class: "stats inline" }, s.rows.map(([k, v]) => h("div", {}, h("dt", {}, k), h("dd", {}, v)))),
    s.note ? h("p", { class: "meta" }, `These figures are ${s.note}.`) : null);
}

/** What one day of a session did, from the map's run input. */
export function dayFigures(run) {
  return [["Places visited this day", String(run.visited)], ["Distance", `${fmt(run.distanceKm)} km`],
    ["Working time", run.workingMinutes == null ? "n/a" : `${fmt(run.workingMinutes / 60)} hours`],
    ["Back at the depot", clock(run.returnMinute) ?? "n/a"]];
}

export const dayFiguresList = (run) =>
  h("dl", { class: "stats" }, dayFigures(run).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));

/** Shown instead of a route for a day the session does not have ("finished on day 3" / "stopped after day 2, did not finish"). */
export function noDayNote(session, day) {
  const t = dayEnding(session, day) || "";
  return h("p", { class: "meta day-ended" }, t ? `${t[0].toUpperCase()}${t.slice(1)}.` : "");
}
