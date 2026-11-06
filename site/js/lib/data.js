// Loads the files the server exposes. Every function caches its promise, so pages share one fetch.
const cache = new Map();

function once(key, load) {
  if (!cache.has(key)) cache.set(key, load());
  return cache.get(key);
}

async function getJson(url, optional = false) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    if (optional) return null;
    throw new Error(`Could not load ${url} (${res.status}). Run the harness first, or start the server with --results.`);
  }
  return res.json();
}

/** results/index.json: one summary row per run. */
export const loadIndex = () => once("index", () => getJson("/results/index.json"));

/** Declared metadata, keyed by algorithm id (from each algorithm.json). */
export const loadAlgorithms = () => once("algorithms", async () =>
  Object.fromEntries((await getJson("/api/algorithms", true) || []).map((a) => [a.id, a])));

/** results/aggregates-<experiment>.json, or null when absent. */
export const loadAggregate = (experiment) =>
  once("agg:" + experiment, () => getJson(`/results/aggregates-${encodeURIComponent(experiment)}.json`, true));

/** One full run record (route, schedule, stderr...). `file` comes from the index. */
export const loadRun = (file) => once("run:" + file, () => getJson(`/results/${encodeURIComponent(file)}`));

export async function experimentNames() {
  const { runs } = await loadIndex();
  return [...new Set(runs.map((r) => r.experiment).filter(Boolean))].sort();
}
