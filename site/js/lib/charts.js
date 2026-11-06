// Hand-rolled SVG line charts (no library, works offline). Colours come from CSS tokens --s1..--s6 in css/charts.css.
import { h } from "./dom.js";

const NS = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) el.setAttribute(k, v);
  el.append(...kids.flat().filter(Boolean));
  return el;
};

const SHAPES = ["circle", "square", "diamond", "triangle", "cross", "circle"];
/** Identity of an algorithm on every chart: colour, marker shape and dash, fixed by its position in the sorted id list. */
export function styleFor(index) {
  return { color: `var(--s${(index % 6) + 1})`, shape: SHAPES[index % 6], dash: index >= 6 ? "6 3" : null };
}

function marker(shape, x, y, color, r = 4.5) {
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
 * Returns a <figure> holding the chart, a hover/keyboard tooltip and a table view.
 */
export function lineChart(opts) {
  const { series, log = false, guides = [], formatY = compact } = opts;
  const W = 560, H = 300, m = { l: 52, r: 16, t: 26, b: 40 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const xs = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
  const ys = series.flatMap((s) => s.points.flatMap((p) => [p.y, p.hi]).filter((v) => typeof v === "number"))
    .concat(guides.flatMap((g) => g.points.map((p) => p.y)));
  const fig = h("figure", { class: "chart" }, h("figcaption", {}, opts.title));
  if (!xs.length || !ys.length) {
    fig.append(h("p", { class: "muted chart-empty" }, opts.emptyText || "No data to chart."));
    return fig;
  }

  // scales
  let xp, yp, yTicks;
  const xmin = xs[0], xmax = xs[xs.length - 1];
  if (log) {
    const lx0 = Math.log10(xmin), lx1 = Math.log10(xmax === xmin ? xmin * 2 : xmax);
    xp = (x) => m.l + ((Math.log10(x) - lx0) / (lx1 - lx0)) * pw;
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
    "aria-label": `${opts.title}. Use left and right arrow keys to move between customer counts.` });
  const grid = svg("g", { class: "grid" });
  yTicks.forEach((t) => {
    grid.append(svg("line", { x1: m.l, x2: W - m.r, y1: yp(t), y2: yp(t) }),
      svg("text", { x: m.l - 8, y: yp(t) + 4, "text-anchor": "end" }, formatY(t)));
  });
  xs.forEach((x) => {
    grid.append(svg("line", { x1: xp(x), x2: xp(x), y1: H - m.b, y2: H - m.b + 4, class: "tick" }),
      svg("text", { x: xp(x), y: H - m.b + 18, "text-anchor": "middle" }, String(x)));
  });
  grid.append(svg("text", { x: m.l + pw / 2, y: H - 4, "text-anchor": "middle", class: "axis-title" }, opts.xLabel || "Customers"));
  root.append(grid, svg("text", { x: 4, y: 11, class: "axis-title" }, opts.yLabel));
  root.append(svg("line", { class: "axis", x1: m.l, x2: m.l, y1: m.t, y2: H - m.b }),
    svg("line", { class: "axis", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }));

  const marks = svg("g");
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
    marks.append(svg("polyline", { fill: "none", stroke: col, "stroke-width": 2, "stroke-linejoin": "round",
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
    tip.replaceChildren(h("strong", {}, `${x} customers`), ...rows.map(({ s, p }) => h("div", { class: "tip-row" },
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
      h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Customers"), series.map((s) => h("th", { scope: "col" }, s.name)))),
      h("tbody", {}, xs.map((x) => h("tr", {}, h("th", { scope: "row" }, x), series.map((s) => {
        const p = s.points.find((q) => q.x === x);
        return h("td", {}, p ? formatY(p.y) + (p.lo != null ? ` ±${formatY(p.y - p.lo)}` : "") : "n/a");
      })))))));

  fig.append(wrap, legend, table);
  if (guides.length) fig.append(h("p", { class: "chart-note" }, "Dotted lines show each algorithm's declared growth rate, anchored at its smallest measured size."));
  return fig;
}
