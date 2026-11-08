import { h, fmt, select } from "../lib/dom.js";
import { loadAggregate, loadAlgorithms, experimentNames } from "../lib/data.js";
import { buildSeries, logLogSeries, declaredExponent } from "../lib/scaling.js";
import { lineChart, styleFor } from "../lib/charts.js";
import { getView, viewLabel, viewCountText } from "../lib/view.js";
import { hasFull } from "../lib/fullrun.js";
import { fullSeries, maxMean, computeUnit, stoppedNotes } from "../lib/fullscaling.js";

const METRICS = [
  { key: "visited", title: "Customers visited", yLabel: "Mean customers visited" },
  { key: "distanceKm", title: "Distance", yLabel: "Mean distance (km)" },
  { key: "totalMinutes", title: "Total time", yLabel: "Mean total time (min)" },
  { key: "runtimeMs", title: "Runtime", yLabel: "Mean runtime (ms)" },
];

function declaredText(a) {
  return a?.complexity?.time ? `declared time ${a.complexity.time}` : "complexity not declared";
}

function scalingPlots(groups, algs, names, styles) {
  const nameOf = (id) => algs[id]?.displayName || id;
  const mk = (metric, title, yLabel, withGuides) => {
    const data = logLogSeries(groups, metric);
    const series = data.filter((d) => d.points.length).map((d) => ({
      id: d.algorithmId, name: nameOf(d.algorithmId), style: styles[d.algorithmId], points: d.points }));
    const guides = withGuides ? series.flatMap((s) => {
      const e = declaredExponent(algs[s.id]?.complexity?.time);
      const first = s.points[0], last = s.points[s.points.length - 1];
      if (e == null || s.points.length < 2) return [];
      return [{ id: s.id, style: s.style, points: [first, last].map((p) => ({ x: p.x, y: first.y * (p.x / first.x) ** e })) }];
    }) : [];
    const fig = lineChart({ title, yLabel, series, guides, log: true,
      emptyText: metric === "work" ? "No algorithm reported a work count (nodesExpanded or iterations), so there is nothing to plot." : "No positive runtimes to plot." });
    const notes = data.map((d) => {
      const bits = [];
      if (d.slope != null) bits.push(`measured growth about n^${fmt(d.slope, 2)}`);
      else if (d.points.length) bits.push("one size only, growth not measurable");
      if (metric === "work") bits.push(d.key ? `counting ${d.key}` : "no work count reported");
      if (d.skipped.length && d.points.length) bits.push(`no value at ${d.skipped.join(", ")} customers`);
      if (withGuides) bits.push(declaredText(algs[d.algorithmId]));
      return h("li", {}, h("i", { class: "sw", style: `background:${styles[d.algorithmId].color}` }),
        h("span", {}, h("strong", {}, nameOf(d.algorithmId)), ": ", bits.join("; ")));
    });
    fig.append(h("ul", { class: "scale-list" }, notes));
    return fig;
  };
  return h("div", { class: "chart-grid" },
    mk("runtimeMs", "Measured runtime vs declared complexity (log-log)", "Mean runtime (ms, log scale)", true),
    mk("work", "Measured work vs declared complexity (log-log)", "Mean work count (log scale)", true));
}

// ---- "Until every place is visited": four charts from the full-run aggregates (fullscaling.js) ----
function renderFull(el, ctx, { names, exp, agg, algs }) {
  const title = h("h1", {}, "Scaling");
  const toolbar = names.length > 1 ? [h("div", { class: "toolbar" }, select("Experiment", names.map((n) => ({ value: n, label: n })), exp,
    (v) => ctx.navigate(`scaling?experiment=${encodeURIComponent(v)}`)))] : [];
  if (!hasFull(agg)) {
    el.append(title, h("p", { class: "lede" }, "How long each algorithm needs to visit every place, as the number of customers grows."), ...toolbar,
      h("div", { class: "empty card", role: "status" },
        "The \"", viewLabel("full"), "\" results have not been produced yet. Run ", h("code", {}, "python3 start.py"),
        " to make them, then reload this page."));
    return;
  }
  const full = agg.full;
  const ids = [...new Set(full.groups.map((g) => g.algorithmId))].sort();
  const styles = Object.fromEntries(ids.map((id, i) => [id, styleFor(i)]));
  const nameOf = Object.fromEntries(ids.map((id) => [id, algs[id]?.displayName || id]));
  const unit = computeUnit(maxMean(full.groups, "totalRuntimeMs"));
  const METRICS_FULL = [
    { key: "workingHours", title: "Working hours needed (headline)", yLabel: "Mean working hours", scale: 1 },
    { key: "days", title: "Days needed", yLabel: "Mean days", scale: 1 },
    { key: "totalDistanceKm", title: "Total distance", yLabel: "Mean distance (km)", scale: 1 },
    { key: "totalRuntimeMs", title: `Total compute time (${unit.label})`, yLabel: `Mean compute time (${unit.label})`, scale: unit.factor },
  ];
  const charts = METRICS_FULL.map((m) => {
    const fig = lineChart({ title: m.title, yLabel: m.yLabel,
      series: fullSeries(full, m.key, m.scale).map((s) => ({ ...s, id: s.algorithmId, name: nameOf[s.algorithmId], style: styles[s.algorithmId] })),
      emptyText: "No example finished, so there is nothing to chart." });
    fig.append(h("p", { class: "chart-note" }, "Band or bars: one sample standard deviation across the examples that finished. Shown only where at least 2 finished."));
    return fig;
  });
  const notes = stoppedNotes(full, nameOf);
  el.append(title,
    h("p", { class: "lede" }, "How long each algorithm needs to visit every place, as the number of customers grows. Working hours are travelling plus waiting, with nights left out. Hover a chart or use the left and right arrow keys to read values."),
    ...toolbar,
    h("div", { class: "chart-grid" }, charts),
    notes.length
      ? h("div", { class: "card stopped-notes", role: "note" }, h("h2", {}, "Examples that did not finish"),
          h("ul", {}, notes.map((n) => h("li", {}, n))),
          h("p", { class: "meta" }, "These examples are never drawn as a time. A size where none finished has no point."))
      : h("p", { class: "meta" }, "Every example finished, so every size has a point."),
    h("p", { class: "meta" }, `Experiment ${exp}: ${viewLabel("full")}, ${viewCountText("full", agg)}.`));
}

export default {
  path: "scaling",
  title: "Scaling",
  fullView: "ready",
  async render(el, ctx) {
    const names = await experimentNames();
    if (!names.length) {
      el.append(h("h1", {}, "Scaling"), h("div", { class: "empty card" },
        "No experiment results found. Run ", h("code", {}, "python3 -m harness.experiment scaling"), " first."));
      return;
    }
    const exp = names.includes(ctx.params.get("experiment")) ? ctx.params.get("experiment") : names[0];
    const agg = await loadAggregate(exp);
    if (!agg) throw new Error(`No aggregates-${exp}.json found next to the run results.`);
    const algs = await loadAlgorithms();
    if (getView() === "full") return renderFull(el, ctx, { names, exp, agg, algs });
    const ids = [...new Set(agg.groups.map((g) => g.algorithmId))].sort();
    const styles = Object.fromEntries(ids.map((id, i) => [id, styleFor(i)]));
    const nameOf = (id) => algs[id]?.displayName || id;

    const charts = METRICS.map((m) => lineChart({
      title: m.title, yLabel: m.yLabel,
      series: buildSeries(agg.groups, m.key).map((s) => ({ ...s, id: s.algorithmId, name: nameOf(s.algorithmId), style: styles[s.algorithmId] })),
      emptyText: "No valid runs, so there is nothing to chart.",
    }));
    charts.forEach((c, i) => { if (METRICS[i].key !== "runtimeMs") c.append(h("p", { class: "chart-note" }, "Band or bars: one sample standard deviation across instances. Shown only where at least 2 runs exist.")); });

    el.append(
      h("h1", {}, "Scaling"),
      h("p", { class: "lede" }, "How each algorithm behaves as the number of customers grows. Hover a chart or use the left and right arrow keys to read values."),
      ...(names.length > 1 ? [h("div", { class: "toolbar" }, select("Experiment", names.map((n) => ({ value: n, label: n })), exp,
        (v) => ctx.navigate(`scaling?experiment=${encodeURIComponent(v)}`)))] : []),
      h("div", { class: "chart-grid" }, charts),
      h("h2", {}, "Measured growth against declared complexity"),
      h("p", { class: "meta" }, "Both axes are logarithmic, so a straight line's slope is the growth exponent. Failed runs are left out of the quality means; runtime and work include every run that reported them. Sizes with a zero or missing value cannot appear on a log axis and are listed under the chart."),
      scalingPlots(agg.groups, algs, nameOf, styles),
      h("p", { class: "meta" }, `Experiment ${exp}: ${agg.parameters?.instancesPerSize ?? "?"} instances per size.`));
  },
};
