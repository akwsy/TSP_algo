import { h, fmt, select } from "../lib/dom.js";
import { loadAggregate, loadAlgorithms, experimentNames } from "../lib/data.js";
import { rankGroups, groupBadges } from "../lib/model.js";

const meanSd = (s, digits) => s && typeof s.mean === "number"
  ? [h("span", { class: "num-strong" }, fmt(s.mean, digits)),
     typeof s.std === "number" ? h("span", { class: "sd" }, ` ±${fmt(s.std, digits)}`) : null]
  : h("span", { class: "muted" }, "n/a");

const TONE = { ok: "badge ok", bad: "badge bad", warn: "badge warn", note: "badge" };

function failureCell(g) {
  return groupBadges(g).map((b) => h("span", { class: TONE[b.tone], style: "display:block;margin-bottom:2px" }, b.text));
}

function table(groups, algs, size) {
  const rows = rankGroups(groups);
  return h("div", { class: "card table-wrap" }, h("table", {},
    h("caption", {}, `Ranked by mean visits, then shorter mean distance, with algorithms that had any failed run ranked below those valid on every run. ${size} customers. Failed runs are left out of the means, never counted as zero visits.`),
    h("thead", {}, h("tr", {},
      h("th", { scope: "col" }, "Rank"), h("th", { scope: "col", class: "l" }, "Algorithm"),
      h("th", { scope: "col", class: "l" }, "Declared complexity"),
      h("th", { scope: "col" }, "Visits (mean)"), h("th", { scope: "col" }, "Distance km"),
      h("th", { scope: "col" }, "Total min"), h("th", { scope: "col" }, "Runtime ms"),
      h("th", { scope: "col" }, "Failures"))),
    h("tbody", {}, rows.map((g) => {
      const a = algs[g.algorithmId] || {};
      const cx = a.complexity;
      return h("tr", { class: g.rank === 1 ? "best" : "" },
        h("td", { class: "rank" }, g.rank ?? "-"),
        h("td", { class: "l name" }, a.displayName || g.algorithmId, h("small", {}, g.algorithmId)),
        h("td", { class: "l" }, cx ? [`time ${cx.time}`, h("small", { class: "muted", style: "display:block" }, `space ${cx.space}`)]
          : h("span", { class: "muted" }, "not declared")),
        h("td", {}, meanSd(g.visited, 2)), h("td", {}, meanSd(g.distanceKm, 1)),
        h("td", {}, meanSd(g.totalMinutes, 0)), h("td", {}, meanSd(g.runtimeMs, 1)),
        h("td", { class: "wrap" }, failureCell(g)));
    }))));
}

export default {
  path: "overview",
  title: "Overview",
  async render(el, ctx) {
    const names = await experimentNames();
    if (!names.length) {
      el.append(h("h1", {}, "Overview"), h("div", { class: "empty card" },
        "No experiment results found. Run ", h("code", {}, "python3 -m harness.experiment scaling"), " first."));
      return;
    }
    const exp = names.includes(ctx.params.get("experiment")) ? ctx.params.get("experiment") : names[0];
    const agg = await loadAggregate(exp);
    if (!agg) throw new Error(`No aggregates-${exp}.json found next to the run results.`);
    const algs = await loadAlgorithms();
    const sizes = agg.sizes;
    const want = Number(ctx.params.get("size"));
    const size = sizes.includes(want) ? want : sizes[sizes.length - 1];
    const go = (e, s) => ctx.navigate(`overview?experiment=${encodeURIComponent(e)}&size=${s}`);

    el.append(
      h("h1", {}, "Overview"),
      h("p", { class: "lede" }, "Every algorithm on the same instances. Pick a size to compare them at that number of customers."),
      h("div", { class: "toolbar" },
        names.length > 1 ? select("Experiment", names.map((n) => ({ value: n, label: n })), exp, (v) => go(v, size)) : null,
        select("Customers", sizes.map((n) => ({ value: n, label: `${n} customers` })), size, (v) => go(exp, v))),
      table(agg.groups.filter((g) => g.numCustomers === size), algs, size),
      h("p", { class: "meta" }, `Experiment ${exp}: ${agg.parameters?.instancesPerSize ?? "?"} instances per size. ± is the sample standard deviation across instances.`));
  },
};
