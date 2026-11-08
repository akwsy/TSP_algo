// Motion and theme logic (pure, no DOM). Tested by tests/test_site_motion.py.
// Every animation on the site is decoration over a final state that is already correct: when motion is off, the page simply
// shows that final state. These helpers decide timing and whether motion runs at all.

/**
 * When each leg of a route starts and how long it takes to draw, in visiting order.
 * Legs draw back to back at up to maxLegMs each; a long route is squeezed so the whole draw fits budgetMs, and past
 * minLegMs per leg the legs overlap (still in order) rather than running over the budget.
 */
export function revealSchedule(legCount, { budgetMs = 2400, maxLegMs = 420, minLegMs = 40 } = {}) {
  if (!(legCount > 0)) return [];
  const duration = Math.round(Math.min(maxLegMs, Math.max(minLegMs, budgetMs / legCount)));
  const step = duration * legCount <= budgetMs ? duration : (budgetMs - duration) / Math.max(1, legCount - 1);
  return Array.from({ length: legCount }, (_, i) => ({ start: Math.round(i * step), duration }));
}

/** Ease-out cubic: fast start, gentle landing. */
export const easeOut = (t) => 1 - (1 - t) ** 3;

/** The number a count-up shows at progress t (0..1). It lands exactly on the target. */
export function countUpValue(target, t) {
  const p = Math.min(1, Math.max(0, t));
  return p === 1 ? target : target * easeOut(p);
}

/** Motion runs only when the system does not ask to reduce it and the visitor has not chosen "reduce" on the site. */
export function motionAllowed(systemReduce, stored) {
  return !systemReduce && stored !== "reduce";
}

/** Entrance delay for the i-th row of a list: a short step per row, capped so long lists never wait long. */
export const staggerDelay = (i, stepMs = 40, capMs = 400) => Math.min(capMs, i * stepMs);

export const THEMES = ["dark", "light", "system"];
/** The stored theme choice, or dark (the site's default look) when nothing valid is stored. */
export const resolveTheme = (stored) => (THEMES.includes(stored) ? stored : "dark");
/** The theme button cycles dark, light, system. */
export const nextTheme = (current) => THEMES[(THEMES.indexOf(resolveTheme(current)) + 1) % THEMES.length];
