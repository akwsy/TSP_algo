import { h, select } from "../lib/dom.js";
import { loadIndex, loadRun } from "../lib/data.js";
import { failedRuns, failureKind, shortCommit } from "../lib/model.js";

const BADGE = { "timed out": "warn", crashed: "bad", invalid: "bad" };

function item(run, rec) {
  const kind = failureKind(run);
  const reason = run.failureReason || (kind === "timed out" ? "Exceeded the time limit." : "No reason recorded.");
  const stderr = rec && rec.stderr && rec.stderr.trim();
  return h("li", { class: "card fail" },
    h("div", { class: "fail-head" },
      h("span", { class: `badge ${BADGE[kind]}` }, kind),
      h("strong", {}, run.algorithmId), h("span", {}, `on ${run.instanceId}`),
      h("span", { class: "meta" }, [run.timestamp, run.commit ? `commit ${shortCommit(run.commit)}` : null].filter(Boolean).join(" | "))),
    h("p", { class: "fail-reason" }, reason),
    stderr
      ? h("details", {}, h("summary", {}, "Captured stderr"), h("pre", {}, stderr))
      : h("p", { class: "meta" }, rec ? "Nothing was written to stderr." : "stderr could not be loaded."));
}

export default {
  path: "failures",
  title: "Failures",
  async render(el, ctx) {
    const { runs } = await loadIndex();
    const all = failedRuns(runs).sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""));
    el.append(h("h1", {}, "Failures"),
      h("p", { class: "lede" }, "Runs that were invalid, crashed or timed out, with the reason the harness recorded. These never count as zero visits anywhere on the site."));
    if (!all.length) {
      el.append(h("div", { class: "empty card" }, "No failed runs. Every recorded run was valid."));
      return;
    }
    const kinds = ["all", ...new Set(all.map(failureKind))];
    const algsInList = ["all", ...new Set(all.map((r) => r.algorithmId))];
    const kind = kinds.includes(ctx.params.get("kind")) ? ctx.params.get("kind") : "all";
    const alg = algsInList.includes(ctx.params.get("algorithm")) ? ctx.params.get("algorithm") : "all";
    const go = (k, a) => ctx.navigate(`failures?kind=${encodeURIComponent(k)}&algorithm=${encodeURIComponent(a)}`);
    const shown = all.filter((r) => (kind === "all" || failureKind(r) === kind) && (alg === "all" || r.algorithmId === alg));
    const records = await Promise.all(shown.map((r) => loadRun(r.file).catch(() => null)));

    el.append(
      h("div", { class: "toolbar" },
        select("Kind", kinds.map((k) => ({ value: k, label: k === "all" ? "All kinds" : k })), kind, (v) => go(v, alg)),
        select("Algorithm", algsInList.map((a) => ({ value: a, label: a === "all" ? "All algorithms" : a })), alg, (v) => go(kind, v))),
      h("p", { class: "meta", role: "status" }, `${shown.length} of ${all.length} failed runs`),
      shown.length ? h("ul", { class: "fail-list" }, shown.map((r, i) => item(r, records[i])))
        : h("div", { class: "empty card" }, "No failed runs match these filters."));
  },
};
