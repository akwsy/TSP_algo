// Compare: the algorithms side by side over the whole series of experiments (results/suite.json and its aggregates files).
// Every figure and sentence comes from lib/compare.js (pure, tested); this file only lays them out.
import { h } from "../lib/dom.js";
import { loadSuite, loadAggregateFile, loadAlgorithms } from "../lib/data.js";
import * as C from "../lib/compare.js";
import { lineChart, scatterChart, styleFor, marker, compact } from "../lib/charts.js";
import { replaceHashParams } from "../lib/instances.js";
import { setView } from "../lib/view.js";
import { stagger, countUp, motionOn } from "../lib/fx.js";

const NS = "http://www.w3.org/2000/svg";
const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
/** The algorithm's chart identity (colour plus marker shape) as a small inline mark. */
function algMark(style, size = 14) {
  const s = document.createElementNS(NS, "svg");
  s.setAttribute("width", size); s.setAttribute("height", size); s.setAttribute("viewBox", "0 0 14 14");
  s.setAttribute("aria-hidden", "true"); s.setAttribute("class", "alg-mark");
  s.append(marker(style.shape, 7, 7, style.color, 4.5));
  return s;
}

const emptyState = () => h("div", { class: "empty card", role: "status" },
  h("p", {}, "No experiment series has been run yet, so there is nothing to compare."),
  h("p", {}, "Run ", h("code", {}, "python3 start.py --suite"), " (or ", h("code", {}, "python3 -m harness.experiment suite"),
    ") to run every experiment, then reload this page."));

/** A link into the Instance page for one example. The examples here are first-day results, so the link opens that view. */
const exampleLink = (id, text) => h("a", { href: `#/instance?id=${encodeURIComponent(id)}`, onclick: () => setView("first") }, text);

function section(id, title, lede, ...body) {
  return h("section", { class: "cmp-section", "aria-labelledby": id },
    h("h2", { id }, title), lede ? h("p", { class: "meta cmp-lede" }, lede) : null, ...body);
}

// ---- 1. headline ----
function headlineBlock(model, names, styles, algs) {
  const hl = C.headline(model, names, algs);
  const t = C.totals(model);
  const order = C.standings(model).overall;
  const cell = (label, value, note) => h("div", {}, h("dt", {}, label), h("dd", { class: "count" }, value), note ? h("dd", {}, h("small", {}, note)) : null);
  return h("section", { class: "card takeaway", "aria-labelledby": "cmp-takeaway" },
    h("h2", { id: "cmp-takeaway", class: "eyebrow" }, "The takeaway"),
    h("p", { class: "takeaway-text" }, hl.text),
    h("ol", { class: "standing", "aria-label": "Overall standing" }, order.map((o, i) =>
      h("li", { class: i === 0 ? "first" : null }, algMark(styles[o.id], 16), h("span", {}, hl.standing[i])))),
    h("dl", { class: "readout cmp-readout", "aria-label": "Size of the series" },
      cell("Experiments", t.experiments.toLocaleString("en")), cell("Settings tried", t.settings.toLocaleString("en")),
      cell("Runs", t.runs.toLocaleString("en")), cell("Algorithms", t.algorithms.toLocaleString("en"))),
    hl.caveats.length ? h("ul", { class: "caveats", "aria-label": "Caveats" }, hl.caveats.map((c) => h("li", {}, c))) : null);
}

// ---- 2. profiles ----
function firstSentence(text) {
  const m = String(text || "").match(/^.*?[.!?](\s|$)/);
  return (m ? m[0] : String(text || "")).trim();
}
function profileCards(model, names, styles, algs) {
  const order = C.standings(model).overall.map((o) => o.id);
  const all = C.profiles(model);
  return h("div", { class: "profile-grid" }, order.map((id, i) => all.find((p) => p.id === id)).map((p, i) => {
    const a = algs[p.id] || {};
    const cx = a.complexity;
    return h("article", { class: "card profile", "aria-labelledby": `prof-${p.id}` },
      h("h3", { id: `prof-${p.id}` }, h("span", { class: i === 0 ? "place first" : "place" }, C.ordinal(i + 1)), algMark(styles[p.id], 16), names[p.id]),
      h("p", { class: "profile-id mono" }, p.id),
      h("p", { class: "profile-desc" }, a.description ? firstSentence(a.description) : "No description declared."),
      h("div", { class: "profile-tags" },
        h("span", { class: "badge" }, cx?.time ? `time ${cx.time}` : "complexity not declared"),
        a.exact === true ? h("span", { class: "badge ok" }, "exact") : a.exact === false ? h("span", { class: "badge" }, "not exact: a heuristic") : null),
      h("dl", { class: "facts" }, C.profileFacts(p, names).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])));
  }));
}

// ---- 3. head-to-head grid ----
function headToHead(model, names, styles, ctx) {
  const params = ctx.params;
  const order = C.standings(model).overall.map((o) => o.id);
  const ids = model.algorithms;
  const state = {
    exp: model.experiments.find((e) => e.name === params.get("exp")) || model.experiments[0],
    value: null, row: params.get("row"), col: params.get("col"),
  };
  const pickValue = (e, want) => (e.values.includes(want) ? want : e.values[Math.floor((e.values.length - 1) / 2)]);
  state.value = pickValue(state.exp, Number(params.get("at")));
  if (!ids.includes(state.row) || !ids.includes(state.col) || state.row === state.col) [state.row, state.col] = [order[0], order[1] ?? order[0]];

  const host = h("div", { class: "h2h" });
  const detail = h("div", { class: "card h2h-detail", role: "region", "aria-live": "polite", "aria-label": "Selected comparison" });
  const expSel = h("select", { onchange: (e) => { state.exp = model.experiments.find((x) => x.name === e.target.value); state.value = pickValue(state.exp, state.value); valueOptions(); draw(); } },
    model.experiments.map((e) => h("option", { value: e.name, selected: e === state.exp }, C.experimentTitle(e.name))));
  const valSel = h("select", { onchange: (e) => { state.value = Number(e.target.value); draw(); } });
  const valueOptions = () => valSel.replaceChildren(...state.exp.values.map((v) =>
    h("option", { value: v, selected: v === state.value }, C.sweepLabel(state.exp.param, v))));
  valueOptions();

  function sync() {
    const p = new URLSearchParams(location.hash.split("?")[1] || "");
    p.set("exp", state.exp.name); p.set("at", String(state.value)); p.set("row", state.row); p.set("col", state.col);
    replaceHashParams("compare", p);
  }

  function showDetail() {
    const cell = C.pairCell(state.exp.agg, state.value, state.row, state.col);
    const A = names[state.row], B = names[state.col];
    const where = C.sweepLabel(state.exp.param, state.value);
    const kids = [h("h3", {}, algMark(styles[state.row]), `${A} against ${B}`, h("span", { class: "muted" }, cap(where)))];
    if (!cell) kids.push(h("p", {}, `${A} and ${B} were not compared here (${where}).`));
    else {
      kids.push(...C.pairSummary(cell, names).map((s) => h("p", {}, s)));
      kids.push(h("h4", {}, "Examples with the biggest gap"));
      kids.push(cell.gaps.length
        ? h("ol", { class: "gap-list" }, cell.gaps.map((g) => h("li", {},
          exampleLink(g.instanceId, `Example ${g.instanceId}`), ": ",
          `${A} ${g.rowVisited}, ${B} ${g.colVisited} `,
          h("span", { class: g.difference > 0 ? "delta better" : "delta worse" },
            `(${Math.abs(g.difference)} ${g.difference > 0 ? "more" : "fewer"} for ${A})`))))
        : h("p", { class: "muted" }, "No example where they visited a different number of places."));
    }
    detail.replaceChildren(...kids);
  }

  function draw(focusKey) {
    const table = h("table", { class: "h2h-grid" },
      h("caption", {}, `${C.experimentTitle(state.exp.name)}, ${C.sweepLabel(state.exp.param, state.value)}. Each cell reads across: the row's algorithm against the column's. `,
        "It shows the average difference in places visited with its margin of error, and wins-ties-losses. Select a cell for the details."),
      h("thead", {}, h("tr", {}, h("th", { scope: "col", class: "l" }, h("span", { class: "sr-only" }, "Row algorithm against column algorithm"), h("span", { "aria-hidden": "true" }, "Row vs column")),
        order.map((c) => h("th", { scope: "col" }, h("span", { class: "col-head" }, algMark(styles[c]), names[c]))))),
      h("tbody", {}, order.map((r, ri) => h("tr", {}, h("th", { scope: "row", class: "l" }, h("span", { class: "row-head" }, algMark(styles[r]), names[r])),
        order.map((c, ci) => {
          if (r === c) return h("td", { class: "h2h-self" }, h("span", { "aria-hidden": "true" }, "—"), h("span", { class: "sr-only" }, "same algorithm"));
          const cell = C.pairCell(state.exp.agg, state.value, r, c);
          const lab = C.cellLabel(cell, names);
          const selected = r === state.row && c === state.col;
          return h("td", { class: `h2h-cell tone-${lab.tone}` }, h("button", {
            type: "button", class: "h2h-btn", "aria-pressed": String(selected), "aria-label": lab.aria, "data-r": ri, "data-c": ci,
            onclick: () => { state.row = r; state.col = c; draw(`${ri},${ci}`); },
          }, h("span", { class: "h2h-verdict" }, h("span", { class: "h2h-icon", "aria-hidden": "true" }, lab.icon), lab.word),
          h("span", { class: "h2h-diff" }, lab.diff, h("small", {}, " places")),
          h("span", { class: "h2h-margin" }, lab.margin),
          h("span", { class: "h2h-record" }, lab.record, h("small", {}, " W-T-L"))));
        })))));
    // Arrow keys move between the cells of the grid (Tab still reaches each one).
    table.addEventListener("keydown", (e) => {
      const b = e.target.closest?.(".h2h-btn");
      if (!b) return;
      const step = { ArrowRight: [0, 1], ArrowLeft: [0, -1], ArrowDown: [1, 0], ArrowUp: [-1, 0] }[e.key];
      if (!step) return;
      e.preventDefault();
      let r = Number(b.dataset.r), c = Number(b.dataset.c);
      for (let k = 0; k < order.length * order.length; k++) {
        r = (r + step[0] + order.length) % order.length; c = (c + step[1] + order.length) % order.length;
        const next = table.querySelector(`.h2h-btn[data-r="${r}"][data-c="${c}"]`);
        if (next) { next.focus(); break; }
      }
    });
    host.replaceChildren(h("div", { class: "card table-wrap" }, table));
    if (focusKey) host.querySelector(`.h2h-btn[data-r="${focusKey.split(",")[0]}"][data-c="${focusKey.split(",")[1]}"]`)?.focus();
    showDetail();
    sync();
  }
  draw();
  return [
    h("div", { class: "toolbar" }, h("label", {}, "Experiment", expSel), h("label", {}, "Setting", valSel)),
    h("ul", { class: "legend tone-legend", "aria-label": "How to read a cell" },
      h("li", {}, h("span", { class: "tone-chip tone-more", "aria-hidden": "true" }, "▲"), "more places, beyond the margin of error"),
      h("li", {}, h("span", { class: "tone-chip tone-even", "aria-hidden": "true" }, "≈"), "too close to call"),
      h("li", {}, h("span", { class: "tone-chip tone-fewer", "aria-hidden": "true" }, "▼"), "fewer places, beyond the margin of error")),
    h("div", { class: "h2h-layout" }, host, detail),
  ];
}

// ---- 4. experiment gallery ----
function experimentCard(e, names, styles) {
  const metricKey = `cmp-${e.name}`;
  const chartHost = h("div", { class: "exp-chart" });
  const METRICS = {
    visited: { label: "Places visited", draw: () => {
      const fig = lineChart({ title: `${C.experimentTitle(e.name)}: average places visited`, yLabel: "Average places visited", xLabel: C.sweepAxis(e.param),
        series: C.experimentSeries(e, "visited").map((s) => ({ ...s, id: s.algorithmId, name: names[s.algorithmId], style: styles[s.algorithmId] })),
        formatX: (x) => C.sweepLabel(e.param, x), tickX: (x) => C.sweepTick(e.param, x), xName: C.sweepAxis(e.param), xKeys: "settings",
        emptyText: "No valid runs, so there is nothing to chart." });
      fig.append(h("p", { class: "chart-note" }, "Band: one standard deviation either side of the average, across the examples."));
      return fig;
    } },
    runtime: { label: "Run time", draw: () => {
      const fig = lineChart({ title: `${C.experimentTitle(e.name)}: average run time`, yLabel: "Average run time (ms, log scale)", xLabel: C.sweepAxis(e.param),
        series: C.experimentSeries(e, "runtimeMs").map((s) => ({ ...s, points: s.points.filter((p) => p.y > 0).map((p) => ({ ...p, lo: null, hi: null })),
          id: s.algorithmId, name: names[s.algorithmId], style: styles[s.algorithmId] })),
        logY: true, formatY: compact, formatX: (x) => C.sweepLabel(e.param, x), tickX: (x) => C.sweepTick(e.param, x), xName: C.sweepAxis(e.param), xKeys: "settings",
        emptyText: "No run times to plot." });
      fig.append(h("p", { class: "chart-note" }, "Log scale: each grid line is ten times the one below. Run time is measured from outside, so it includes starting the program."));
      return fig;
    } },
  };
  let current = "visited";
  const buttons = {};
  const show = (key, focus) => {
    current = key;
    for (const [k, b] of Object.entries(buttons)) { b.setAttribute("aria-checked", String(k === key)); b.tabIndex = k === key ? 0 : -1; }
    const fig = METRICS[key].draw();
    fig.classList.remove("card");
    chartHost.replaceChildren(fig);
    if (focus) buttons[key].focus();
  };
  const keys = Object.keys(METRICS);
  const toggle = h("div", { class: "seg", role: "radiogroup", "aria-label": `Chart for ${C.experimentTitle(e.name)}` },
    keys.map((k) => (buttons[k] = h("button", { type: "button", role: "radio", class: "seg-opt", "data-key": metricKey,
      onclick: () => show(k), onkeydown: (ev) => {
        const i = keys.indexOf(current);
        const next = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? keys[(i + 1) % keys.length]
          : ev.key === "ArrowLeft" || ev.key === "ArrowUp" ? keys[(i - 1 + keys.length) % keys.length] : null;
        if (next) { ev.preventDefault(); show(next, true); }
      } }, METRICS[k].label))));
  show("visited");
  return h("article", { class: "card exp-card", "aria-labelledby": `exp-${e.name}` },
    h("h3", { id: `exp-${e.name}` }, C.experimentTitle(e.name)),
    h("p", { class: "exp-question" }, C.experimentQuestion(e)),
    h("p", { class: "meta" }, C.settingsText(e)),
    h("p", { class: "exp-takeaway" }, h("span", { class: "badge" }, "Result"), " ", C.experimentTakeaway(e, names)),
    toggle, chartHost);
}

// ---- 5. trade-off ----
function tradeoffBlock(model, names, styles, ctx) {
  const want = ctx.params.get("trade") || "all";
  const host = h("div", { class: "tradeoff" });
  const sel = h("select", { onchange: (e) => draw(e.target.value) },
    h("option", { value: "all" }, "All experiments (average of every setting)"),
    model.experiments.map((e) => h("optgroup", { label: C.experimentTitle(e.name) },
      e.values.map((v) => h("option", { value: `${e.name}|${v}` }, `${C.experimentTitle(e.name)}: ${C.sweepLabel(e.param, v)}`)))));
  function draw(key) {
    const [name, v] = key === "all" ? [null, null] : key.split("|");
    const exp = model.experiments.find((e) => e.name === name);
    const k = exp && exp.values.includes(Number(v)) ? key : "all";
    sel.value = k;
    const points = k === "all" ? C.tradeoff(model, null, null) : C.tradeoff(model, exp.name, Number(v));
    const where = k === "all" ? "averaged over every setting of every experiment" : `${C.experimentTitle(exp.name)}, ${C.sweepLabel(exp.param, Number(v))}`;
    const fig = scatterChart({ title: `Run time against places visited, ${where}`, xLabel: "Average run time (ms, log scale)", yLabel: "Average places visited",
      points: points.map((p) => ({ id: p.id, name: names[p.id], style: styles[p.id], x: p.runtimeMs, y: p.visited, frontier: p.frontier })),
      formatX: C.msText, formatY: compact, emptyText: "No run times to plot." });
    host.replaceChildren(h("div", { class: "tradeoff-layout" }, fig,
      h("div", { class: "card frontier-notes" }, h("h3", {}, "Reading it"),
        h("ul", {}, [...C.frontierText(points, names), ...C.frontierSteps(points, names)].map((t) => h("li", {}, t))),
        h("p", { class: "meta" }, "Up is more places, left is faster. An algorithm is on the efficient frontier when no other one is both at least as fast and visits at least as many places."))));
    const p = new URLSearchParams(location.hash.split("?")[1] || "");
    if (k === "all") p.delete("trade"); else p.set("trade", k);
    replaceHashParams("compare", p);
  }
  draw(want);
  return [h("div", { class: "toolbar" }, h("label", {}, "Setting", sel)), host];
}

// ---- 6. where they differ ----
function differBlock(model, names, styles) {
  const list = (rows, who, other, side) => rows.length
    ? h("ol", { class: "gap-list" }, rows.map((g) => {
      const mine = side === "a" ? g.aVisited : g.bVisited, theirs = side === "a" ? g.bVisited : g.aVisited;
      return h("li", {}, h("span", { class: "gap-size" }, `+${Math.abs(g.difference)}`), " ",
        exampleLink(g.instanceId, `Example ${g.instanceId}`),
        h("span", { class: "muted" }, `${cap(C.sweepLabel(g.param, g.value))}: ${who} ${mine}, ${other} ${theirs}`));
    }))
    : h("p", { class: "muted" }, `${who} never visited more places than ${other} in the examples listed.`);
  return h("div", { class: "differ-grid" }, C.pairGaps(model, 3).map((p) => {
    const A = names[p.a], B = names[p.b];
    return h("article", { class: "card differ" }, h("h3", {}, algMark(styles[p.a]), A, h("span", { class: "muted" }, " and "), algMark(styles[p.b]), B),
      h("div", { class: "differ-cols" },
        h("div", {}, h("h4", {}, `${A} visited more`), list(p.aAhead, A, B, "a")),
        h("div", {}, h("h4", {}, `${B} visited more`), list(p.bAhead, B, A, "b"))));
  }));
}

export default {
  path: "compare",
  title: "Compare",
  async render(el, ctx) {
    el.append(h("h1", {}, "Compare"),
      h("p", { class: "lede" }, "How the algorithms compare across a series of experiments, each changing one thing about the problem. ",
        "A win means more places visited, or the same number with a shorter drive."));
    const suite = await loadSuite();
    if (!suite || !Array.isArray(suite.experiments) || !suite.experiments.length) { el.append(emptyState()); return; }
    const files = await Promise.all(suite.experiments.map((e) => loadAggregateFile(e.aggregates || `aggregates-${e.name}.json`)));
    const model = C.buildModel(suite, Object.fromEntries(suite.experiments.map((e, i) => [e.name, files[i]])));
    if (!model.experiments.length) {
      el.append(h("div", { class: "empty card", role: "status" }, "The experiment list was found, but none of its results files could be read. Run ",
        h("code", {}, "python3 start.py --suite"), " again, then reload this page."));
      return;
    }
    const algs = await loadAlgorithms();
    const names = Object.fromEntries(model.algorithms.map((id) => [id, algs[id]?.displayName || id]));
    const styles = Object.fromEntries(model.algorithms.map((id, i) => [id, styleFor(i)]));

    el.append(headlineBlock(model, names, styles, algs));
    if (model.missing.length) {
      el.append(h("p", { class: "view-note", role: "note" }, `Not shown, because their results are missing: ${model.missing.map(C.experimentTitle).join(", ")}. Run `,
        h("code", {}, "python3 start.py --suite"), " to produce them."));
    }
    el.append(
      section("cmp-profiles", "The algorithms", "What each one is, and what the measurements say about it over the whole series.", profileCards(model, names, styles, algs)),
      section("cmp-h2h", "Head to head", "Every pair on the same examples. Pick an experiment and a setting, then select a cell.", ...headToHead(model, names, styles, ctx)),
      section("cmp-gallery", "The experiments", "Each experiment changes one thing and keeps the rest fixed. Hover a chart or focus it and use the arrow keys to read values.",
        h("div", { class: "exp-grid" }, model.experiments.map((e) => experimentCard(e, names, styles)))),
      section("cmp-tradeoff", "Speed against results", "Is the extra run time worth it? Each algorithm's average run time against the places it visits.", ...tradeoffBlock(model, names, styles, ctx)),
      section("cmp-differ", "Where they differ", "The examples with the biggest gap in places visited for each pair, across every experiment. Open one to see both routes on the map.",
        differBlock(model, names, styles),
        h("p", { class: "meta" }, "Only the five biggest gaps of each setting are saved with the results, so smaller differences may be missing from these lists.")),
    );
    if (motionOn()) {
      el.querySelectorAll(".cmp-readout .count").forEach((d) => countUp(d, { duration: 700 }));
      el.querySelectorAll(".standing, .profile-grid, .exp-grid").forEach((c) => stagger(c));
    }
  },
};
