import { h, fmt, select } from "../lib/dom.js";
import { loadIndex, loadAlgorithms } from "../lib/data.js";
import { groupRunsByCommit, compareVersions } from "../lib/scaling.js";
import { shortCommit } from "../lib/model.js";

const label = (g) => (g.commit ? shortCommit(g.commit, 8) : "no commit recorded");
const when = (ts) => (ts || "").replace("T", " ").replace(/(\.\d+)?(\+00:00|Z)?$/, " UTC");

function compareTable(c, a, b) {
  // For all three, lower distance/runtime is better and more visits is better.
  const row = (name, m, digits, higherBetter) => {
    const d = m.delta;
    const cls = d == null || Math.abs(d) < 1e-9 ? "" : (d > 0) === higherBetter ? "better" : "worse";
    const word = d == null ? "" : Math.abs(d) < 1e-9 ? "no change" : (d > 0) === higherBetter ? "better" : "worse";
    return h("tr", {}, h("th", { scope: "row", class: "l" }, name),
      h("td", {}, fmt(m.a, digits)), h("td", {}, fmt(m.b, digits)),
      h("td", {}, d == null ? h("span", { class: "muted" }, "n/a")
        : h("span", { class: `delta ${cls}` }, `${d > 0 ? "+" : ""}${fmt(d, digits)}`, word ? ` (${word})` : "")),
      h("td", {}, m.n));
  };
  return h("div", { class: "card" }, h("p", { class: "meta hist-note" }, `Same ${c.sharedInstances} instances in both versions. Means are over instances valid in both versions; runtime over every pair that reported one.`),
    h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", { scope: "col", class: "l" }, "Measure"), h("th", { scope: "col" }, label(a)),
      h("th", { scope: "col" }, label(b)), h("th", { scope: "col" }, "Change"), h("th", { scope: "col" }, "Pairs"))),
    h("tbody", {}, row("Mean visits", c.visited, 2, true), row("Mean distance km", c.distanceKm, 1, false),
      row("Mean runtime ms", c.runtimeMs, 1, false)))));
}

export default {
  path: "history",
  title: "Run history",
  async render(el, ctx) {
    const { runs } = await loadIndex();
    const algs = await loadAlgorithms();
    el.append(h("h1", {}, "Run history"));
    if (!runs.length) {
      el.append(h("div", { class: "empty card" }, "No runs yet. Run the harness first."));
      return;
    }
    const ids = [...new Set(runs.map((r) => r.algorithmId))].sort();
    const alg = ids.includes(ctx.params.get("algorithm")) ? ctx.params.get("algorithm") : ids[0];
    const groups = groupRunsByCommit(runs.filter((r) => r.algorithmId === alg));
    const keyOf = (g) => g.key;
    const pick = (name, dflt) => groups.find((g) => g.key === ctx.params.get(name)) || dflt;
    const a = pick("a", groups[1] || groups[0]);
    const b = pick("b", groups[0]);
    const go = (over) => {
      const q = new URLSearchParams({ algorithm: alg, a: a.key, b: b.key, ...over });
      ctx.navigate(`history?${q}`);
    };
    const opts = groups.map((g) => ({ value: keyOf(g), label: `${label(g)} - ${when(g.last)} (${g.runs.length} runs)` }));

    el.append(
      h("p", { class: "lede" }, "Every run labelled by the algorithm's commit and when it ran. Pick two versions to see what a change did on the same instances."),
      h("div", { class: "toolbar" },
        select("Algorithm", ids.map((id) => ({ value: id, label: algs[id]?.displayName || id })), alg,
          (v) => ctx.navigate(`history?algorithm=${encodeURIComponent(v)}`))),
      h("h2", {}, "Compare two versions"),
      h("div", { class: "toolbar" },
        select("Before", opts, a.key, (v) => go({ a: v })), select("After", opts, b.key, (v) => go({ b: v }))));

    if (groups.length < 2) {
      el.append(h("div", { class: "empty card" }, "Only one version of this algorithm has been run, so there is nothing to compare yet. Commit a change and run the experiment again."));
    } else if (a.key === b.key) {
      el.append(h("div", { class: "empty card" }, "Choose two different versions."));
    } else {
      const c = compareVersions(a.runs, b.runs);
      el.append(c.sharedInstances
        ? h("div", {}, compareTable(c, a, b),
          h("p", { class: "meta" }, `${c.onlyA} instances only in the before version and ${c.onlyB} only in the after version are ignored. Failed on shared instances: ${c.failedA} before, ${c.failedB} after.${a.commit && b.commit ? "" : " A version without a recorded commit may mix several code states."}`))
        : h("div", { class: "empty card" }, "These two versions did not run any of the same instances, so they cannot be compared."));
    }

    el.append(h("h2", {}, "Versions, newest first"),
      ...groups.map((g) => h("section", { class: "card hist-commit", "aria-label": `${label(g)} ${g.algorithmId}` },
        h("div", { class: "hist-head" }, h("span", { class: "mono num-strong" }, label(g)),
          h("span", { class: "muted" }, `${when(g.first)}${g.first === g.last ? "" : ` to ${when(g.last)}`}`),
          h("span", { class: g.valid === g.runs.length ? "badge ok" : "badge warn" }, `${g.valid} of ${g.runs.length} valid`)),
        h("details", {}, h("summary", {}, "Runs"), h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Instance"), h("th", { scope: "col" }, "Visits"),
            h("th", { scope: "col" }, "Distance km"), h("th", { scope: "col" }, "Runtime ms"), h("th", { scope: "col" }, "Time"))),
          h("tbody", {}, [...g.runs].sort((x, y) => x.instanceId.localeCompare(y.instanceId, "en", { numeric: true })).map((r) => h("tr", {},
            h("td", {}, r.instanceId), h("td", {}, r.valid ? r.visited : "invalid"), h("td", {}, fmt(r.distanceKm, 1)),
            h("td", {}, fmt(r.runtimeMs, 1)), h("td", {}, when(r.timestamp)))))))))));
  },
};
