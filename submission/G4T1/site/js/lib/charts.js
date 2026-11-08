// Hand-rolled SVG line charts (no library, works offline). Colours come from CSS tokens --s1..--s6 in css/charts.css.
import { h } from "./dom.js";
import { algorithmStyle } from "./algstyle.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) el.setAttribute(k, v);
  el.append(...kids.flat().filter(Boolean));
  return el;
};

/** Identity of an algorithm on every chart: colour, marker shape and dash, fixed by its position in the sorted id list
 *  (shared with the maps, see algstyle.js). */
export function styleFor(index) {
  const s = algorithmStyle(index);
  return { color: `var(--s${s.colorIndex + 1})`, shape: s.shape, dash: s.dash || null };
}

export function marker(shape, x, y, color, r = 4.5) {
  const common = { fill: color, stroke: "var(--surface)", "stroke-width": 1.5 };
  if (shape === "square") return svg("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, ...common });
  if (shape === "diamond") return svg("path", { d: `M${x} ${y - r - 1}L${x + r + 1} ${y}L${x} ${y + r + 1}L${x - r - 1} ${y}Z`, ...common });
  if (shape === "triangle") return svg("path", { d: `M${x} ${y - r - 1}L${x + r + 1} ${y + r}L${x - r - 1} ${y + r}Z`, ...common });
  if (shape === "cross") return svg("path", { d: `M${x - r} ${y}H${x + r}M${x} ${y - r}V${y + r}`, stroke: color, "stroke-width": 3, fill: "none" });
  return svg("circle", { cx: x, cy: y, r, ...common });
}

export function niceMax(v) {
  if (!(v > 0)) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  const f = v / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

export const compact = (v) => {
  const a = Math.abs(v);
  if (a >= 1e6) return `${+(v / 1e6).toPrecision(3)}M`;
  if (a >= 1e4) return `${+(v / 1e3).toPrecision(3)}k`;
  if (a >= 100) return String(Math.round(v));
  if (a >= 1) return String(+v.toPrecision(3));
  if (a === 0) return "0";
  return String(+v.toPrecision(2));
};

/**
 * opts: { title, yLabel, xLabel, series:[{id,name,style,points:[{x,y,lo,hi,note}]}], log:boolean,
 *         guides:[{id,style,points:[{x,y}],label}], formatY(v) }
 * The x axis is the number of customers unless told otherwise: logY (log y axis on a linear x axis), formatX(x) (the
 * tooltip heading, default "<x> customers"), tickX(x) (axis tick text), xName (table head) and xKeys (what the arrow
 * keys step through, for the accessible name).
 * Returns a <figure> holding the chart, a hover/keyboard tooltip and a table view.
 */
export function lineChart(opts) {
  const { series, log = false, guides = [], formatY = compact, logY = log, formatX = (x) => `${x} customers`, tickX = String,
    xName = "Customers", xKeys = "customer counts" } = opts;
  const W = 560, H = 300, m = { l: 52, r: 16, t: 26, b: 40 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const ys = series.flatMap((s) => s.points.flatMap((p) => [p.y, p.hi]).filter((v) => typeof v === "number"))
    .concat(guides.flatMap((g) => g.points.map((p) => p.y)));
  const fig = h("figure", { class: "chart card" }, h("figcaption", {}, opts.title));
  if (!xs.length || !ys.length) {
    fig.append(h("p", { class: "muted chart-empty" }, opts.emptyText || "No data to chart."));
    return fig;
  }

  // scales
  let xp, yp, yTicks;
  const xmin = xs[0], xmax = xs[xs.length - 1];
  if (logY) {
    const lx0 = Math.log10(xmin), lx1 = Math.log10(xmax === xmin ? xmin * 2 : xmax);
    xp = log ? (x) => m.l + ((Math.log10(x) - lx0) / (lx1 - lx0)) * pw
      : (x) => m.l + (xmax === xmin ? pw / 2 : ((x - xmin) / (xmax - xmin)) * pw);
    const pos = ys.filter((v) => v > 0);
    const lo = Math.floor(Math.log10(Math.min(...pos))), hi = Math.max(lo + 1, Math.ceil(Math.log10(Math.max(...pos))));
    yp = (y) => m.t + ph - ((Math.log10(y) - lo) / (hi - lo)) * ph;
    yTicks = Array.from({ length: hi - lo + 1 }, (_, i) => 10 ** (lo + i));
  } else {
    const ymax = niceMax(Math.max(...ys));
    const ymin = 0; // every charted measure is non-negative; a band below zero is clipped at the axis
    xp = (x) => m.l + (xmax === xmin ? pw / 2 : ((x - xmin) / (xmax - xmin)) * pw);
    yp = (y) => m.t + ph - ((Math.max(y, ymin) - ymin) / (ymax - ymin)) * ph;
    yTicks = Array.from({ length: 5 }, (_, i) => ymin + ((ymax - ymin) * i) / 4);
  }

  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "group", tabindex: 0,
    "aria-label": `${opts.title}. Use left and right arrow keys to move between ${xKeys}.` });
  const grid = svg("g", { class: "grid" });
  yTicks.forEach((t) => {
    grid.append(svg("line", { x1: m.l, x2: W - m.r, y1: yp(t), y2: yp(t) }),
      svg("text", { x: m.l - 8, y: yp(t) + 4, "text-anchor": "end" }, formatY(t)));
  });
  xs.forEach((x) => {
    grid.append(svg("line", { x1: xp(x), x2: xp(x), y1: H - m.b, y2: H - m.b + 4, class: "tick" }),
      svg("text", { x: xp(x), y: H - m.b + 18, "text-anchor": "middle" }, tickX(x)));
  });
  grid.append(svg("text", { x: m.l + pw / 2, y: H - 4, "text-anchor": "middle", class: "axis-title" }, opts.xLabel || "Customers"));
  root.append(grid, svg("text", { x: 4, y: 11, class: "axis-title" }, opts.yLabel));
  root.append(svg("line", { class: "axis", x1: m.l, x2: m.l, y1: m.t, y2: H - m.b }),
    svg("line", { class: "axis", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));

  const marks = svg("g", { class: "marks" }); // drawn in left to right by CSS (charts.css); final state without motion
  for (const g of guides) {
    marks.append(svg("polyline", { class: "guide", fill: "none", stroke: g.style.color, "stroke-width": 1.5, "stroke-dasharray": "2 4",
      points: g.points.map((p) => `${xp(p.x)},${yp(p.y)}`).join(" ") }));
  }
  for (const s of series) {
    const col = s.style.color;
    const withBand = s.points.length >= 2 && s.points.every((p) => p.lo != null);
    if (withBand) {
      const top = s.points.map((p) => `${xp(p.x)},${yp(p.hi)}`);
      const bot = s.points.map((p) => `${xp(p.x)},${yp(p.lo)}`).reverse();
      marks.append(svg("polygon", { points: [...top, ...bot].join(" "), fill: col, opacity: 0.15 }));
    } else {
      for (const p of s.points) if (p.lo != null && p.hi != null) {
        marks.append(svg("path", { d: `M${xp(p.x)} ${yp(p.lo)}V${yp(p.hi)}M${xp(p.x) - 4} ${yp(p.lo)}H${xp(p.x) + 4}M${xp(p.x) - 4} ${yp(p.hi)}H${xp(p.x) + 4}`,
          stroke: col, "stroke-width": 1.5, fill: "none" }));
      }
    }
    marks.append(svg("polyline", { class: "series-line", style: `color:${col}`, fill: "none", stroke: col, "stroke-width": 2, "stroke-linejoin": "round",
      "stroke-dasharray": s.style.dash, points: s.points.map((p) => `${xp(p.x)},${yp(p.y)}`).join(" ") }));
    for (const p of s.points) marks.append(marker(s.style.shape, xp(p.x), yp(p.y), col));
  }
  root.append(marks);

  // hover / keyboard layer: crosshair at the nearest customer count and one tooltip listing every series there
  const cross = svg("line", { class: "crosshair", y1: m.t, y2: H - m.b, visibility: "hidden" });
  root.append(cross);
  const tip = h("div", { class: "chart-tip", role: "status", hidden: true });
  const wrap = h("div", { class: "chart-wrap" }, root, tip);
  let cur = -1;
  const show = (i) => {
    cur = Math.max(0, Math.min(xs.length - 1, i));
    const x = xs[cur];
    cross.setAttribute("x1", xp(x)); cross.setAttribute("x2", xp(x)); cross.setAttribute("visibility", "visible");
    const rows = series.map((s) => ({ s, p: s.points.find((q) => q.x === x) }));
    tip.replaceChildren(h("strong", {}, formatX(x)), ...rows.map(({ s, p }) => h("div", { class: "tip-row" },
      h("i", { class: "sw", style: `background:${s.style.color}` }), h("span", {}, s.name),
      h("b", {}, p ? formatY(p.y) + (p.lo != null ? ` ±${formatY(p.y - p.lo)}` : p.note ? ` ${p.note}` : "") : "n/a"))));
    tip.hidden = false;
    const frac = xp(x) / W;
    tip.style.left = `${frac * 100}%`;
    tip.style.transform = `translateX(${frac > 0.6 ? "-105%" : "5%"})`;
  };
  const hide = () => { cur = -1; cross.setAttribute("visibility", "hidden"); tip.hidden = true; };
  root.addEventListener("pointermove", (e) => {
    const r = root.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    let best = 0;
    xs.forEach((x, i) => { if (Math.abs(xp(x) - px) < Math.abs(xp(xs[best]) - px)) best = i; });
    show(best);
  });
  root.addEventListener("pointerleave", () => { if (document.activeElement !== root) hide(); });
  root.addEventListener("focus", () => show(cur < 0 ? 0 : cur));
  root.addEventListener("blur", hide);
  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") { show(cur + 1); e.preventDefault(); }
    else if (e.key === "ArrowLeft") { show(cur - 1); e.preventDefault(); }
    else if (e.key === "Escape") hide();
  });

  const legend = h("ul", { class: "legend" }, series.map((s) => h("li", {},
    svg("svg", { width: 22, height: 12, viewBox: "0 0 22 12", "aria-hidden": "true" },
      svg("line", { x1: 0, x2: 22, y1: 6, y2: 6, stroke: s.style.color, "stroke-width": 2, "stroke-dasharray": s.style.dash }),
      marker(s.style.shape, 11, 6, s.style.color, 3.5)), s.name)));

  const table = h("details", { class: "chart-table" }, h("summary", {}, "Table view"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, xName), series.map((s) => h("th", { scope: "col" }, s.name)))),
      h("tbody", {}, xs.map((x) => h("tr", {}, h("th", { scope: "row" }, tickX(x)), series.map((s) => {
        const p = s.points.find((q) => q.x === x);
        return h("td", {}, p ? formatY(p.y) + (p.lo != null ? ` ±${formatY(p.y - p.lo)}` : "") : "n/a");
      })))))));

  fig.append(wrap, legend, table);
  if (guides.length) fig.append(h("p", { class: "chart-note" }, "Dotted lines show each algorithm's declared growth rate, anchored at its smallest measured size."));
  return fig;
}

/** Tick values for a log axis: 1, 2, 5 times each power of ten inside [lo, hi] (just the powers when that is many). */
function logTicks(lo, hi) {
  const out = [];
  for (let p = Math.floor(Math.log10(lo)); p <= Math.ceil(Math.log10(hi)); p++) for (const f of [1, 2, 5]) out.push(f * 10 ** p);
  const inside = out.filter((t) => t >= lo * 0.999 && t <= hi * 1.001);
  return inside.length > 7 ? inside.filter((t) => Number.isInteger(Math.log10(t))) : inside;
}

/**
 * Scatter of one point per algorithm: x on a log scale, y linear from zero. Points with frontier === true get a ring
 * and are joined by a dashed line. opts: { title, xLabel, yLabel, points:[{id,name,style,x,y,frontier}], formatX, formatY,
 *   frontierLabel }. Arrow keys step through the points from left to right. Returns a <figure> with a table view.
 */
export function scatterChart(opts) {
  const { formatX = compact, formatY = compact, frontierLabel = "Efficient frontier" } = opts;
  const pts = opts.points.filter((p) => typeof p.x === "number" && p.x > 0 && typeof p.y === "number").sort((a, b) => a.x - b.x);
  const fig = h("figure", { class: "chart card scatter" }, h("figcaption", {}, opts.title));
  if (!pts.length) { fig.append(h("p", { class: "muted chart-empty" }, opts.emptyText || "No data to chart.")); return fig; }
  const W = 560, H = 320, m = { l: 52, r: 24, t: 26, b: 42 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const x0 = Math.min(...pts.map((p) => p.x)) / 1.6, x1 = Math.max(...pts.map((p) => p.x)) * 1.6;
  const lx0 = Math.log10(x0), lx1 = Math.log10(x1);
  const xp = (x) => m.l + ((Math.log10(x) - lx0) / (lx1 - lx0)) * pw;
  const ymax = niceMax(Math.max(...pts.map((p) => p.y)) * 1.08);
  const yp = (y) => m.t + ph - (Math.max(0, y) / ymax) * ph;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "group", tabindex: 0,
    "aria-label": `${opts.title}. Use left and right arrow keys to move between algorithms.` });
  const grid = svg("g", { class: "grid" });
  for (let i = 0; i <= 4; i++) {
    const t = (ymax * i) / 4;
    grid.append(svg("line", { x1: m.l, x2: W - m.r, y1: yp(t), y2: yp(t) }), svg("text", { x: m.l - 8, y: yp(t) + 4, "text-anchor": "end" }, formatY(t)));
  }
  for (const t of logTicks(x0, x1)) {
    grid.append(svg("line", { x1: xp(t), x2: xp(t), y1: H - m.b, y2: H - m.b + 4, class: "tick" }),
      svg("text", { x: xp(t), y: H - m.b + 18, "text-anchor": "middle" }, formatX(t)));
  }
  grid.append(svg("text", { x: m.l + pw / 2, y: H - 4, "text-anchor": "middle", class: "axis-title" }, opts.xLabel));
  root.append(grid, svg("text", { x: 4, y: 11, class: "axis-title" }, opts.yLabel),
    svg("line", { class: "axis", x1: m.l, x2: m.l, y1: m.t, y2: H - m.b }), svg("line", { class: "axis", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));
  const marks = svg("g", { class: "marks" });
  const front = pts.filter((p) => p.frontier === true);
  if (front.length > 1) marks.append(svg("polyline", { class: "frontier-line", fill: "none", points: front.map((p) => `${xp(p.x)},${yp(p.y)}`).join(" ") }));
  // Direct labels: right of the point (left near the right edge), pushed apart when two would overlap.
  const labels = pts.map((p) => ({ p, x: xp(p.x), y: yp(p.y), right: xp(p.x) < W - 170 }));
  [...labels].sort((a, b) => a.y - b.y).forEach((l, i, arr) => {
    for (const o of arr.slice(0, i)) if (Math.abs(o.y - l.y) < 15 && Math.abs(o.x - l.x) < 160) l.y = o.y + 15;
  });
  for (const l of labels) {
    if (l.p.frontier === true) marks.append(svg("circle", { class: "frontier-ring", cx: l.x, cy: yp(l.p.y), r: 10 }));
    marks.append(marker(l.p.style.shape, l.x, yp(l.p.y), l.p.style.color, 6));
    marks.append(svg("text", { class: "point-label", x: l.x + (l.right ? 15 : -15), y: l.y + 4, "text-anchor": l.right ? "start" : "end" }, l.p.name));
  }
  root.append(marks);
  const cross = svg("circle", { class: "point-focus", r: 14, visibility: "hidden" });
  root.append(cross);
  const tip = h("div", { class: "chart-tip", role: "status", hidden: true });
  const wrap = h("div", { class: "chart-wrap" }, root, tip);
  const frontierWord = (p) => (p.frontier === true ? "on the frontier" : p.frontier === false ? "off the frontier" : "");
  let cur = -1;
  const show = (i) => {
    cur = Math.max(0, Math.min(pts.length - 1, i));
    const p = pts[cur];
    cross.setAttribute("cx", xp(p.x)); cross.setAttribute("cy", yp(p.y)); cross.setAttribute("visibility", "visible");
    tip.replaceChildren(h("strong", {}, p.name),
      h("div", { class: "tip-row" }, h("i", { class: "sw", style: `background:${p.style.color}` }), h("span", {}, "Run time"), h("b", {}, formatX(p.x))),
      h("div", { class: "tip-row" }, h("i", { class: "sw", style: `background:${p.style.color}` }), h("span", {}, "Places visited"), h("b", {}, formatY(p.y))),
      frontierWord(p) ? h("div", { class: "tip-row" }, h("span", {}, frontierWord(p))) : null);
    tip.hidden = false;
    const frac = xp(p.x) / W;
    tip.style.left = `${frac * 100}%`;
    tip.style.transform = `translateX(${frac > 0.6 ? "-105%" : "5%"})`;
  };
  const hide = () => { cur = -1; cross.setAttribute("visibility", "hidden"); tip.hidden = true; };
  root.addEventListener("pointermove", (e) => {
    const r = root.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W, py = ((e.clientY - r.top) / r.height) * H;
    let best = 0;
    pts.forEach((p, i) => { if (Math.hypot(xp(p.x) - px, yp(p.y) - py) < Math.hypot(xp(pts[best].x) - px, yp(pts[best].y) - py)) best = i; });
    show(best);
  });
  root.addEventListener("pointerleave", () => { if (document.activeElement !== root) hide(); });
  root.addEventListener("focus", () => show(cur < 0 ? 0 : cur));
  root.addEventListener("blur", hide);
  root.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { show(cur + 1); e.preventDefault(); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { show(cur - 1); e.preventDefault(); }
    else if (e.key === "Escape") hide();
  });
  const legend = h("ul", { class: "legend" }, pts.map((p) => h("li", {},
    svg("svg", { width: 14, height: 14, viewBox: "0 0 14 14", "aria-hidden": "true" }, marker(p.style.shape, 7, 7, p.style.color, 4.5)), p.name)),
    front.length ? h("li", {}, svg("svg", { width: 26, height: 14, viewBox: "0 0 26 14", "aria-hidden": "true" },
      svg("line", { class: "frontier-line", x1: 0, x2: 26, y1: 7, y2: 7 }), svg("circle", { class: "frontier-ring", cx: 13, cy: 7, r: 5 })), frontierLabel) : null);
  const table = h("details", { class: "chart-table" }, h("summary", {}, "Table view"),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Algorithm", "Run time", "Places visited", "Frontier"].map((t, i) => h("th", { scope: "col", class: i ? null : "l" }, t)))),
      h("tbody", {}, opts.points.map((p) => h("tr", {}, h("th", { scope: "row", class: "l" }, p.name),
        h("td", {}, typeof p.x === "number" ? formatX(p.x) : "n/a"), h("td", {}, typeof p.y === "number" ? formatY(p.y) : "n/a"),
        h("td", {}, p.frontier === true ? "on" : p.frontier === false ? "off" : "n/a")))))));
  fig.append(wrap, legend, table);
  return fig;
}
