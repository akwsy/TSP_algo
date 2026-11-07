import { h, fmt, select } from "../lib/dom.js";
import { loadIndex, loadRun, loadSessionsIndex, loadSession } from "../lib/data.js";
import { loadInstance, ensureMapCss, replaceHashParams } from "../lib/instances.js";
import { algorithmColorIndex } from "../lib/mapmodel.js";
import { createRouteMap, entryStyle, algorithmSwatch, slotLegend } from "../lib/routemap.js";
import { runStats } from "../lib/rundisplay.js";
import { getView } from "../lib/view.js";
import { latestPerAlgorithm, sessionInstanceIds, maxDays, clampDay, dayRun, doneBefore } from "../lib/sessiondays.js";
import { daySelect, sessionBlock, dayFigures, dayFiguresList, noDayNote } from "../lib/fullview.js";

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

/** Per-day comparison for the overlaid map: one row per shown algorithm. */
function dayCompareTable(rows) {
  const head = ["Algorithm", "Places visited this day", "Distance", "Working time", "Back at the depot"];
  return h("div", { class: "card table-wrap spaced" }, h("table", {},
    h("caption", {}, "What each shown algorithm did on the chosen day."),
    h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { scope: "col", class: i ? null : "l" }, t)))),
    h("tbody", {}, rows.map((r) => h("tr", {}, h("td", { class: "l" }, algorithmSwatch(r.entry), r.entry.id),
      r.run ? dayFigures(r.run).map(([, v]) => h("td", {}, v)) : h("td", { colspan: 4, class: "l" }, noDayNote(r.entry.session, r.day).textContent))))));
}

/** Instance explorer for the "Until every place is visited" view: each algorithm's saved session, one day at a time. */
async function renderFull(el, ctx) {
  ensureMapCss();
  const index = await loadSessionsIndex();
  el.append(h("h1", {}, "Instance explorer"),
    h("p", { class: "lede" }, "Every algorithm's answer to one problem, day by day until every place is visited."));
  const ids = sessionInstanceIds(index);
  if (!ids.length) { el.append(h("div", { class: "empty card" }, "No full runs have been saved yet.")); return; }
  const colorIdx = algorithmColorIndex([...new Set(index.map((r) => r.algorithmId))]);
  const state = {
    id: ids.includes(ctx.params.get("id")) ? ctx.params.get("id") : ids[0],
    mode: ctx.params.get("mode") === "overlay" ? "overlay" : "side",
    hidden: new Set((ctx.params.get("hide") || "").split(",").filter(Boolean)),
    day: clampDay(ctx.params.get("day"), 999),
  };
  const forceSvg = ctx.params.get("map") === "svg";
  const body = h("div", {});
  const toggles = h("fieldset", { class: "toggles" });
  const dayHost = h("span", { class: "day-host" });
  let maps = [];
  let token = 0;
  let dayMax = -1;

  function sync() {
    const p = new URLSearchParams({ id: state.id, mode: state.mode, day: String(state.day) });
    if (state.hidden.size) p.set("hide", [...state.hidden].join(","));
    if (forceSvg) p.set("map", "svg");
    replaceHashParams("instance", p);
  }

  async function draw(rebuildToggles, animate = true) {
    const mine = ++token;
    maps.forEach((m) => m.destroy());
    maps = [];
    const latest = latestPerAlgorithm(index, state.id);
    const algIds = latest.map((e) => e.algorithmId);
    let instance, sessions;
    try {
      [instance, sessions] = await Promise.all([loadInstance(state.id), Promise.all(latest.map((e) => loadSession(e.file)))]);
    } catch (err) {
      body.replaceChildren(h("div", { class: "error", role: "alert" }, err.message));
      return;
    }
    if (mine !== token) return;
    if (rebuildToggles) {
      toggles.replaceChildren(h("legend", {}, "Algorithms shown"), ...algIds.map((a) => h("label", { class: "check" },
        h("input", { type: "checkbox", checked: !state.hidden.has(a), onchange: (e) => {
          if (e.target.checked) state.hidden.delete(a); else state.hidden.add(a);
          sync(); draw(false, false);
        } }),
        algorithmSwatch({ id: a, ...entryStyle(colorIdx[a]) }), a)));
    }
    const all = algIds.map((a, i) => ({ id: a, label: a, ...entryStyle(colorIdx[a]), session: sessions[i], seed: latest[i].seed, numCustomers: latest[i].numCustomers }));
    const shown = all.filter((e) => !state.hidden.has(e.id));
    // The selector offers the longest shown session; an algorithm with fewer days says how it ended.
    const max = maxDays(shown.map((e) => e.session));
    state.day = clampDay(state.day, max);
    if (max !== dayMax || rebuildToggles) {
      dayMax = max;
      dayHost.replaceChildren(...(max ? [daySelect(max, state.day, (v) => { state.day = v; sync(); draw(false); })] : []));
    }
    const day = state.day;
    for (const e of shown) {
      e.day = day;
      e.run = dayRun(instance, e.session, day);
      e.done = doneBefore(e.session, day);
    }
    const drawn = shown.filter((e) => e.run);
    const out = [h("p", { class: "meta" }, `${instance.locations.length - 1} customers, departure ${Math.floor(instance.departureMinute / 60)}:00, speed ${instance.speedKmh} km/h.`)];
    if (!shown.length) {
      out.push(h("div", { class: "empty card" }, "No algorithm selected. Tick at least one above."));
    } else if (state.mode === "overlay") {
      out.push(...shown.map((e) => h("section", { class: "alg-card card pad", "aria-label": e.id }, h("h2", { class: "alg-title" }, algorithmSwatch(e), e.id), sessionBlock(e.session))));
      if (drawn.length) {
        const m = createRouteMap(instance, { entries: drawn, forceSvg, animate, summary: false });
        maps.push(m);
        out.push(slotLegend({ day: true }), h("div", { class: "card pad" }, m.el));
      }
      out.push(dayCompareTable(shown.map((e) => ({ entry: e, run: e.run, day }))));
    } else {
      out.push(slotLegend({ day: true }), h("div", { class: "grid" }, shown.map((e) => {
        const card = h("section", { class: "card pad alg-card", "aria-label": e.id }, h("h2", { class: "alg-title" }, algorithmSwatch(e), e.id), sessionBlock(e.session));
        if (e.run) {
          const m = createRouteMap(instance, { entries: [e], forceSvg, animate });
          maps.push(m);
          card.append(h("h3", { class: "day-title" }, `Day ${day}`), m.el, dayFiguresList(e.run),
            h("a", { href: `#/run?algorithm=${encodeURIComponent(e.id)}&example=${e.seed}&places=${e.numCustomers}&day=${day}` }, "Step-by-step schedule"));
        } else {
          card.append(h("h3", { class: "day-title" }, `Day ${day}`), noDayNote(e.session, day));
        }
        return card;
      })));
    }
    body.replaceChildren(...out);
  }

  el.append(
    h("div", { class: "toolbar" },
      select("Problem", ids.map((i) => ({ value: i, label: `${i} (${index.find((x) => x.instanceId === i).numCustomers} customers)` })), state.id,
        (v) => { state.id = v; state.hidden.clear(); state.day = 1; sync(); draw(true); }),
      select("Layout", [{ value: "side", label: "Side by side" }, { value: "overlay", label: "Overlaid on one map" }], state.mode,
        (v) => { state.mode = v; sync(); draw(false); }),
      dayHost),
    toggles, body);
  await draw(true);
  return () => maps.forEach((m) => m.destroy());
}

export default {
  path: "instance",
  title: "Instance explorer",
  fullView: "ready",
  render(el, ctx) { return getView() === "full" ? renderFull(el, ctx) : renderFirst(el, ctx); },
};

async function renderFirst(el, ctx) {
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
}
