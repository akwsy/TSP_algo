// Visual identity of an algorithm on maps and charts (pure, no DOM). Tested by tests/test_site_algstyle.py.
// The six colour-blind-safe colours come first. Every further group of six reuses the colours but
// rotates the dash pattern and the marker shape, so (colour, dash) stays unique for 36 algorithms.

export const DASHES = ["", "9 5", "2 5", "14 4 2 4", "6 3", "1 4"];
export const SHAPES = ["circle", "square", "diamond", "triangle", "cross"];

/** index = position in the sorted list of algorithm ids. */
export function algorithmStyle(index) {
  const colorIndex = index % 6;
  const tier = Math.floor(index / 6);
  return {
    colorIndex,
    dash: DASHES[(colorIndex + tier) % DASHES.length],
    shape: SHAPES[(colorIndex + tier) % SHAPES.length],
  };
}
