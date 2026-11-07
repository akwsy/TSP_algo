// DOM side of the motion layer. Every effect starts from content that is already final and correct: if motion is off,
// these functions return without touching anything. Timing and the on/off rule live in motion.js (tested).
import { countUpValue, staggerDelay } from "./motion.js";

/** True when animation may run (set on <html> by boot.js / app.js from the system setting and the header toggle). */
export const motionOn = () => document.documentElement.dataset.motion !== "reduce";

/** Give each child an index (--i) so CSS can stagger its entrance. The children are visible without this. */
export function stagger(container, { step = 1 } = {}) {
  if (!container) return container;
  [...container.children].forEach((c, i) => c.style.setProperty("--i", String(Math.min(i * step, 14))));
  container.classList.add("stagger");
  return container;
}

/** Count the first number inside `el` up from zero to its value, keeping its formatting (digits, prefix, suffix).
 *  Screen readers get the final text throughout: the moving copy is aria-hidden. */
export function countUp(el, { duration = 800, delay = 0 } = {}) {
  if (!motionOn() || !el) return;
  const text = el.textContent;
  const m = text.match(/-?\d[\d,]*(\.\d+)?/);
  if (!m) return;
  const target = Number(m[0].replace(/,/g, ""));
  const digits = m[1] ? m[1].length - 1 : 0;
  const before = text.slice(0, m.index), after = text.slice(m.index + m[0].length);
  const format = (v) => before + v.toLocaleString("en", { minimumFractionDigits: digits, maximumFractionDigits: digits }) + after;
  const kids = [...el.childNodes];
  const live = document.createElement("span");
  live.setAttribute("aria-hidden", "true");
  const sr = document.createElement("span");
  sr.className = "sr-only";
  sr.textContent = text;
  live.textContent = format(0);
  el.replaceChildren(sr, live);
  const t0 = performance.now() + delay;
  const restore = () => el.replaceChildren(...kids);
  const tick = (now) => {
    if (!el.isConnected) return;
    if (!motionOn()) { restore(); return; }
    const t = (now - t0) / duration;
    if (t >= 1) { restore(); return; }
    live.textContent = format(countUpValue(target, Math.max(0, t)));
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** Count up every element matching `selector` inside root, rows a little after each other. */
export function countUpAll(root, selector, { duration = 800, step = 45, cap = 400 } = {}) {
  if (!motionOn()) return;
  root.querySelectorAll(selector).forEach((el, i) => countUp(el, { duration, delay: 120 + staggerDelay(i, step, cap) }));
}
