// Pure logic for the route detail dropdowns (no DOM). Tested by tests/test_site_runpicker.py.
// Three choices: algorithm, example (the instance seed) and number of places (customer count).
// Options narrow in that order: sizes for the algorithm, then examples for algorithm + size.

const uniqSorted = (xs) => [...new Set(xs)].sort((a, b) => (typeof a === "number" ? a - b : String(a).localeCompare(String(b))));

function nearest(options, want) {
  if (!options.length) return null;
  if (options.includes(want)) return want;
  if (typeof want !== "number") return options[0];
  return options.reduce((best, o) => (Math.abs(o - want) < Math.abs(best - want) ? o : best));
}

/** Options and the matching run file for a (possibly invalid) choice; invalid parts snap to the nearest valid one. */
export function pickerState(runs, choice = {}) {
  const algorithms = uniqSorted(runs.map((r) => r.algorithmId));
  const algorithmId = algorithms.includes(choice.algorithmId) ? choice.algorithmId : algorithms[0] ?? null;
  const ofAlg = runs.filter((r) => r.algorithmId === algorithmId);
  const sizes = uniqSorted(ofAlg.map((r) => r.numCustomers));
  const numCustomers = nearest(sizes, choice.numCustomers);
  const seeds = uniqSorted(ofAlg.filter((r) => r.numCustomers === numCustomers).map((r) => r.seed));
  const seed = nearest(seeds, choice.seed);
  const latest = ofAlg.filter((r) => r.numCustomers === numCustomers && r.seed === seed)
    .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))[0];
  const asked = [["algorithmId", algorithmId], ["seed", seed], ["numCustomers", numCustomers]];
  return { algorithms, sizes, seeds, selected: { algorithmId, seed, numCustomers }, file: latest ? latest.file : null,
    adjusted: asked.some(([k, v]) => choice[k] != null && choice[k] !== v) };
}

/** Choice for an old `?file=` link, or null when that file is not in the index. */
export function choiceFromFile(runs, file) {
  const r = runs.find((x) => x.file === file);
  return r ? { algorithmId: r.algorithmId, seed: r.seed, numCustomers: r.numCustomers } : null;
}
