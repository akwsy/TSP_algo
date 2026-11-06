// Small display helpers shared by the instance explorer and route detail.
import { fmt } from "./dom.js";

export const DASHES = ["", "9 5", "2 5", "14 4 2 4", "6 3", "1 4"];

/** [label, value] rows summarising one valid run record. */
export function runStats(rec) {
  return [
    ["Visited", `${rec.visited}`],
    ["Skipped", (rec.skipped || []).length ? `${rec.skipped.length} (ids ${rec.skipped.join(", ")})` : "none"],
    ["Distance", `${fmt(rec.distanceKm)} km`],
    ["Travel", `${fmt(rec.travelMinutes)} min`],
    ["Waiting", `${fmt(rec.waitMinutes)} min`],
    ["Total", `${fmt(rec.totalMinutes)} min`],
    ["Runtime", `${fmt(rec.runtimeMs)} ms`],
  ];
}
