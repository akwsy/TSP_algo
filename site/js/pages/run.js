import { h, fmt, select } from "../lib/dom.js";
import { loadIndex, loadRun, loadAlgorithms } from "../lib/data.js";
import { loadInstance, ensureMapCss } from "../lib/instances.js";
import { algorithmColorIndex, routeSteps, clock, slotColors } from "../lib/mapmodel.js";
import { createRouteMap, entryStyle } from "../lib/routemap.js";
import { failureKind } from "../lib/model.js";
import { pickerState, choiceFromFile } from "../lib/runpicker.js";

const ROLE = { depart: "Left the depot", stop: "Visit", return: "Back at the depot" };
const REASON = { "timed out": "ran out of time and was stopped", crashed: "stopped with an error", invalid: "gave a route that breaks the rules" };
const num = (v) => (v == null || v === "" ? null : Number(v));

function stepRow(r, deadline) {
  const slot = r.window ? `Open ${clock(r.window[0])}-${clock(r.window[1])}` : "Depot, open all day";
  const late = r.role === "return" && typeof deadline === "number" && r.arrive > deadline;
  return h("tr", {},
    h("td", { class: "l" }, r.role === "stop" ? r.step : ""), h("td", { class: "l" }, ROLE[r.role]),
    h("td", { class: "l name" }, r.name), h("td", { class: "l" }, slot),
    h("td", {}, clock(r.arrive) ?? "-"), h("td", {}, r.wait == null ? "-" : `${fmt(r.wait, 0)} min`),
    h("td", {}, clock(r.leave) ?? "-"), h("td", {}, r.role === "depart" ? "-" : fmt(r.legKm)),
    h("td", {}, fmt(r.cumKm)),
    h("td", { class: "l" }, r.role === "return" ? h("span", { class: `badge ${late ? "bad" : "ok"}` }, late ? "too late" : "on time") : ""));
}

function statsRows(rec) {
  const skipped = rec.skipped || [];
  return [
    ["Places visited", `${rec.visited}`],
    ["Places skipped", skipped.length ? `${skipped.length} (numbers ${skipped.join(", ")})` : "none"],
    ["Distance", `${fmt(rec.distanceKm)} km`],
    ["Driving time", `${fmt(rec.travelMinutes)} min`],
    ["Time spent waiting", `${fmt(rec.waitMinutes)} min`],
    ["Total time", `${fmt(rec.totalMinutes)} min`],
    ["Time to work it out", `${fmt(rec.runtimeMs)} ms`],
  ];
}

function mapKey() {
  const names = ["06:00-10:30", "10:30-15:00", "15:00-19:30", "19:30-24:00"];
  return h("ul", { class: "legend", "aria-label": "Map key" },
    slotColors().map((c, i) => h("li", {}, h("span", { class: "dot filled", style: `background:${c}` }), `Open ${names[i]}`)),
    h("li", {}, h("span", { class: "dot filled", style: "background:var(--muted)" }), "Filled: visited"),
    h("li", {}, h("span", { class: "dot hollow" }), "Hollow: skipped"),
    h("li", {}, h("span", { class: "dot depot" }), "Square: depot"));
}

export default {
  path: "run",
  title: "Route detail",
  async render(el, ctx) {
    ensureMapCss();
    const [{ runs }, algs] = await Promise.all([loadIndex(), loadAlgorithms()]);
    el.append(h("h1", {}, "Route detail"), h("p", { class: "lede" }, "One example, stop by stop. Pick an algorithm, an example and a number of places."));
    if (!runs.length) { el.append(h("div", { class: "empty card" }, "No runs recorded yet.")); return; }
    const asked = choiceFromFile(runs, ctx.params.get("file")) || {
      algorithmId: ctx.params.get("algorithm"), seed: num(ctx.params.get("example")), numCustomers: num(ctx.params.get("places")) };
    const st = pickerState(runs, asked);
    const { algorithmId, seed, numCustomers } = st.selected;
    const nameOf = (id) => algs[id]?.displayName || id;
    const go = (c) => ctx.navigate(`run?algorithm=${encodeURIComponent(c.algorithmId)}&example=${c.seed}&places=${c.numCustomers}`);
    const body = h("div", {});
    el.append(
      h("div", { class: "toolbar" },
        select("Algorithm", st.algorithms.map((id) => ({ value: id, label: nameOf(id) })), algorithmId, (v) => go({ algorithmId: v, seed, numCustomers })),
        select("Example", st.seeds.map((n) => ({ value: n, label: `Example ${n}` })), seed, (v) => go({ algorithmId, seed: Number(v), numCustomers })),
        select("Number of places", st.sizes.map((n) => ({ value: n, label: `${n} places` })), numCustomers, (v) => go({ algorithmId, seed, numCustomers: Number(v) }))),
      body);
    const wanted = Object.entries({ algorithm: asked.algorithmId, example: asked.seed, places: asked.numCustomers }).some(([, v]) => v != null);
    if (!st.file) { body.append(h("div", { class: "empty card" }, "There is no run for this choice.")); return; }
    if (st.adjusted && wanted) {
      body.append(h("p", { class: "meta", role: "status" }, `There is no run for that exact choice, so this shows ${nameOf(algorithmId)}, Example ${seed} with ${numCustomers} places instead.`));
    }
    const meta = runs.find((r) => r.file === st.file);

    let rec, instance;
    try {
      [rec, instance] = await Promise.all([loadRun(st.file), loadInstance(meta.instanceId)]);
    } catch (err) {
      body.append(h("div", { class: "error", role: "alert" }, err.message));
      return;
    }
    const idx = algorithmColorIndex([...new Set(runs.map((r) => r.algorithmId))])[rec.algorithmId] ?? 0;
    const entry = { id: rec.algorithmId, label: nameOf(rec.algorithmId), ...entryStyle(idx), run: rec };
    const map = createRouteMap(instance, { entries: [entry], forceSvg: ctx.params.get("map") === "svg", height: 380 });
    const steps = routeSteps(instance, rec);
    const head = ["#", "What happens", "Place", "Open from-to", "Arrived", "Waited", "Left", "Km from last stop", "Km so far", "Back on time?"];
    const when = (rec.timestamp || "").slice(0, 16).replace("T", " ");
    body.append(
      h("p", { class: "meta" }, `${nameOf(rec.algorithmId)}, Example ${seed} with ${numCustomers} places${when ? `, run on ${when}` : ""}`),
      rec.valid === false
        ? h("p", { class: "fail-reason" }, h("span", { class: "badge bad" }, "no usable answer"), " ",
          `This algorithm ${REASON[failureKind(rec)]}. Test result: ${rec.failureReason || "run failed"}.`)
        : h("dl", { class: "stats inline" }, statsRows(rec).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])),
      mapKey(), h("div", { class: "card pad" }, map.el),
      steps.length
        ? h("div", { class: "card table-wrap spaced" }, h("table", {},
          h("caption", {}, `Be back by ${clock(instance.deadlineMinute)}. "Waited" is time spent standing by at a place until it opens.`),
          h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { scope: "col", class: i < 4 || i === 9 ? "l" : null }, t)))),
          h("tbody", {}, steps.map((r) => stepRow(r, instance.deadlineMinute)))))
        : h("div", { class: "empty card spaced" }, "This run has no route to show."));
    return () => map.destroy();
  },
};
