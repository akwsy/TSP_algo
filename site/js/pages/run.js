import { h, fmt, select } from "../lib/dom.js";
import { loadIndex, loadRun } from "../lib/data.js";
import { loadInstance, ensureMapCss, replaceHashParams } from "../lib/instances.js";
import { algorithmColorIndex, routeSteps, clock } from "../lib/mapmodel.js";
import { createRouteMap, algorithmColor, slotLegend } from "../lib/routemap.js";
import { DASHES, runStats } from "../lib/rundisplay.js";

const ROLE = { depart: "Depart", stop: "Visit", return: "Return" };

function stepRow(r, deadline) {
  const slot = r.window ? `Slot ${r.slot + 1}, ${clock(r.window[0])}-${clock(r.window[1])}` : "Depot, open all day";
  const late = r.role === "return" && typeof deadline === "number" && r.arrive > deadline;
  return h("tr", {},
    h("td", { class: "l" }, r.role === "stop" ? r.step : ""), h("td", { class: "l" }, ROLE[r.role]),
    h("td", { class: "l name" }, r.name), h("td", { class: "l" }, slot),
    h("td", {}, clock(r.arrive) ?? "-"), h("td", {}, r.wait == null ? "-" : `${fmt(r.wait, 0)} min`),
    h("td", {}, clock(r.leave) ?? "-"), h("td", {}, r.role === "depart" ? "-" : fmt(r.legKm)),
    h("td", {}, fmt(r.cumKm)),
    h("td", { class: "l" }, r.role === "return" ? h("span", { class: `badge ${late ? "bad" : "ok"}` }, late ? "after deadline" : "within deadline") : ""));
}

export default {
  path: "run",
  title: "Route detail",
  async render(el, ctx) {
    ensureMapCss();
    const { runs } = await loadIndex();
    el.append(h("h1", {}, "Route detail"), h("p", { class: "lede" }, "One run, stop by stop."));
    if (!runs.length) { el.append(h("div", { class: "empty card" }, "No runs recorded yet.")); return; }
    const sorted = [...runs].sort((a, b) => a.instanceId.localeCompare(b.instanceId) || a.algorithmId.localeCompare(b.algorithmId)
      || (b.timestamp || "").localeCompare(a.timestamp || ""));
    const file = sorted.some((r) => r.file === ctx.params.get("file")) ? ctx.params.get("file") : sorted[0].file;
    const meta = sorted.find((r) => r.file === file);
    const body = h("div", {});
    el.append(
      h("div", { class: "toolbar" }, select("Run", sorted.map((r) => ({ value: r.file,
        label: `${r.algorithmId} on ${r.instanceId} (${(r.timestamp || "").slice(0, 16).replace("T", " ")})` })), file,
      (v) => ctx.navigate(`run?file=${encodeURIComponent(v)}`))),
      body);

    let rec, instance;
    try {
      [rec, instance] = await Promise.all([loadRun(file), loadInstance(meta.instanceId)]);
    } catch (err) {
      body.append(h("div", { class: "error", role: "alert" }, err.message));
      return;
    }
    const idx = algorithmColorIndex([...new Set(runs.map((r) => r.algorithmId))])[rec.algorithmId] ?? 0;
    const entry = { id: rec.algorithmId, label: rec.algorithmId, color: algorithmColor(idx), dash: DASHES[idx % DASHES.length], run: rec };
    const map = createRouteMap(instance, { entries: [entry], forceSvg: ctx.params.get("map") === "svg", height: 380 });
    const steps = routeSteps(instance, rec);
    const head = ["#", "Step", "Location", "Slot / window", "Arrive", "Waiting", "Depart", "Leg km", "Cumulative km", "Return"];
    body.append(
      h("p", { class: "meta" }, [rec.algorithmId, rec.instanceId, rec.timestamp, rec.commit ? `commit ${rec.commit.slice(0, 7)}` : null].filter(Boolean).join(" | ")),
      rec.valid === false
        ? h("p", { class: "fail-reason" }, h("span", { class: "badge bad" }, "no valid answer"), " ", rec.failureReason || "Run failed.")
        : h("dl", { class: "stats inline" }, runStats(rec).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
      slotLegend(), h("div", { class: "card pad" }, map.el),
      steps.length
        ? h("div", { class: "card table-wrap spaced" }, h("table", {},
          h("caption", {}, `Return by ${clock(instance.deadlineMinute)}. Waiting is time idle at a customer before its window opens.`),
          h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { scope: "col", class: i < 4 || i === 9 ? "l" : null }, t)))),
          h("tbody", {}, steps.map((r) => stepRow(r, instance.deadlineMinute)))))
        : h("div", { class: "empty card spaced" }, "This run has no route to show."));
    return () => map.destroy();
  },
};
