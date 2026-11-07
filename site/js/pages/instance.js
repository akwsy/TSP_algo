import { h, fmt, select } from "../lib/dom.js";
import { loadIndex, loadRun } from "../lib/data.js";
import { loadInstance, ensureMapCss, replaceHashParams } from "../lib/instances.js";
import { algorithmColorIndex } from "../lib/mapmodel.js";
import { createRouteMap, entryStyle, algorithmSwatch, slotLegend } from "../lib/routemap.js";
import { runStats } from "../lib/rundisplay.js";

const instanceLabel = (id, runs) => `${id} (${runs.find((x) => x.instanceId === id).numCustomers} customers)`;

function statsList(rec) {
  if (rec.valid === false) {
    return h("p", { class: "fail-reason" }, h("span", { class: "badge bad" }, "no valid answer"), " ", rec.failureReason || "Run failed.");
  }
  return h("dl", { class: "stats" }, runStats(rec).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
}

function compareTable(shown) {
  const head = ["Algorithm", "Skipped", "Travel min", "Wait min", "Runtime ms"];
  return h("div", { class: "card table-wrap spaced" }, h("table", {},
    h("caption", {}, "More detail for each shown algorithm on this problem (places visited, distance and total time are in the comparison above)."),
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { scope: "col", class: i ? null : "l" }, t)))),
    h("tbody", {}, shown.map((e) => {
      const r = e.run;
      const cells = r.valid !== false
        ? [(r.skipped || []).length, fmt(r.travelMinutes), fmt(r.waitMinutes), fmt(r.runtimeMs)]
        : [h("span", { class: "badge bad" }, "failed"), "n/a", "n/a", fmt(r.runtimeMs)];
      return h("tr", {}, h("td", { class: "l" }, algorithmSwatch(e), e.id),
        cells.map((c) => h("td", {}, c)));
    }))));
}

export default {
  path: "instance",
  title: "Instance explorer",
  fullView: "pending",
  async render(el, ctx) {
    ensureMapCss();
    const { runs } = await loadIndex();
    const ids = [...new Set(runs.map((r) => r.instanceId))].sort((a, b) => {
      const ra = runs.find((r) => r.instanceId === a), rb = runs.find((r) => r.instanceId === b);
      return ra.numCustomers - rb.numCustomers || ra.seed - rb.seed;
    });
    el.append(h("h1", {}, "Instance explorer"),
      h("p", { class: "lede" }, "Every algorithm's answer to one problem, on the map and in numbers."));
    if (!ids.length) { el.append(h("div", { class: "empty card" }, "No runs recorded yet.")); return; }

    const colorIdx = algorithmColorIndex([...new Set(runs.map((r) => r.algorithmId))]);
    const state = {
      id: ids.includes(ctx.params.get("id")) ? ctx.params.get("id") : ids[0],
      mode: ctx.params.get("mode") === "overlay" ? "overlay" : "side",
      hidden: new Set((ctx.params.get("hide") || "").split(",").filter(Boolean)),
    };
    const forceSvg = ctx.params.get("map") === "svg";
    const body = h("div", {});
    const toggles = h("fieldset", { class: "toggles" });
    let maps = [];
    let token = 0;

    function sync() {
      const p = new URLSearchParams({ id: state.id, mode: state.mode });
      if (state.hidden.size) p.set("hide", [...state.hidden].join(","));
      if (forceSvg) p.set("map", "svg");
      replaceHashParams("instance", p);
    }

    async function draw(rebuildToggles, animate = true) {
      const mine = ++token;
      maps.forEach((m) => m.destroy());
      maps = [];
      const latest = new Map();
      for (const r of runs.filter((x) => x.instanceId === state.id).sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""))) latest.set(r.algorithmId, r);
      const algIds = [...latest.keys()].sort();
      let instance, recs;
      try {
        [instance, recs] = await Promise.all([loadInstance(state.id), Promise.all(algIds.map((a) => loadRun(latest.get(a).file)))]);
      } catch (err) {
        body.replaceChildren(h("div", { class: "error", role: "alert" }, err.message));
        return;
      }
      if (mine !== token) return;
      if (rebuildToggles) {
        toggles.replaceChildren(h("legend", {}, "Algorithms shown"), ...algIds.map((a) => h("label", { class: "check" },
          h("input", { type: "checkbox", checked: !state.hidden.has(a), onchange: (e) => {
            if (e.target.checked) state.hidden.delete(a); else state.hidden.add(a);
            sync(); draw(false, false); // a tick only changes what is shown: no replay
          } }),
          algorithmSwatch({ id: a, ...entryStyle(colorIdx[a]) }), a)));
      }
      const entries = algIds.map((a, i) => ({ id: a, label: a, ...entryStyle(colorIdx[a]), run: recs[i] }));
      const shown = entries.filter((e) => !state.hidden.has(e.id));
      const out = [h("p", { class: "meta" }, `${instance.locations.length - 1} customers, departure ${Math.floor(instance.departureMinute / 60)}:00, speed ${instance.speedKmh} km/h.`)];
      if (!shown.length) {
        out.push(h("div", { class: "empty card" }, "No algorithm selected. Tick at least one above."));
      } else if (state.mode === "overlay") {
        const m = createRouteMap(instance, { entries: shown, forceSvg, animate });
        maps.push(m);
        out.push(h("div", { class: "card pad" }, m.el), compareTable(shown));
      } else {
        out.push(h("div", { class: "grid" }, shown.map((e) => {
          const m = createRouteMap(instance, { entries: [e], forceSvg, animate });
          maps.push(m);
          return h("section", { class: "card pad alg-card", "aria-label": e.id },
            h("h2", { class: "alg-title" }, algorithmSwatch(e), e.id),
            m.el, statsList(e.run),
            h("a", { href: `#/run?file=${encodeURIComponent(latest.get(e.id).file)}` }, "Step-by-step schedule"));
        })));
      }
      body.replaceChildren(...out);
    }

    el.append(
      h("div", { class: "toolbar" },
        select("Problem", ids.map((i) => ({ value: i, label: instanceLabel(i, runs) })), state.id,
          (v) => { state.id = v; state.hidden.clear(); sync(); draw(true); }),
        select("Layout", [{ value: "side", label: "Side by side" }, { value: "overlay", label: "Overlaid on one map" }], state.mode,
          (v) => { state.mode = v; sync(); draw(false); })),
      toggles, slotLegend(), body);
    await draw(true);
    return () => maps.forEach((m) => m.destroy());
  },
};
