// Interactive route map. Leaflet (pinned, from cdnjs) on label-free tiles when it loads in time, otherwise a plain projected
// SVG drawing of the same scene, so the map never goes blank. Force the fallback with ?map=svg on the page URL.
// The only text on the map is the destination names. Every route is a straight-line path with arrowheads and stop numbers.
import { h } from "./dom.js";
import { buildScene, chooseEngine, project, slotColors, laneOffsets, offsetSegment, summaryRows, differenceNotes, labelPlan, labelSide, TILE_LIMITS, labelsVisible, FADED_OPACITY, stopTimes, stopLine, legDetails, legRows } from "./mapmodel.js";
import { algorithmStyle } from "./algstyle.js";
import { marker } from "./charts.js";
import { revealSchedule } from "./motion.js";
import { motionOn } from "./fx.js";

const LEAFLET = "1.9.4";
const BASE = `https://cdnjs.cloudflare.com/ajax/libs/leaflet/${LEAFLET}/`;
const SVGNS = "http://www.w3.org/2000/svg";
// Subresource integrity for the pinned files (sha512 of the cdnjs files, matching the cdnjs API).
const SRI = {
  js: "sha512-puJW3E/qXDqYp9IfhAI54BJEaWIfloJ7JWs7OeD5i6ruC9JZL1gERT1wjtwXFlh7CjE7ZJ+/vcRZRkIYIb6p4g==",
  css: "sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw==",
};
// Esri World Terrain Base: land relief, water and coastlines only, with no place names, shop icons or road names, and no API key.
// (CARTO's label-free tiles now demand a key; Esri's grey canvas bakes region names into low zoom tiles. Dark mode darkens these tiles in CSS.)
const TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}";
// 1x1 transparent GIF: a tile that fails to load shows the map background instead of the browser's broken-image grey.
const BLANK_TILE = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
const ATTRIBUTION = "Tiles &copy; Esri, USGS, NOAA";
let leafletPromise = null;
let mapCount = 0;

export function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  leafletPromise ??= new Promise((resolve, reject) => {
    const css = h("link", { rel: "stylesheet", href: BASE + "leaflet.min.css", integrity: SRI.css, crossorigin: "" });
    const js = h("script", { src: BASE + "leaflet.min.js", integrity: SRI.js, crossorigin: "" });
    js.onload = () => (window.L ? resolve(window.L) : reject(new Error("Leaflet missing")));
    js.onerror = () => reject(new Error("Leaflet failed to load"));
    document.head.append(css, js);
  });
  leafletPromise.catch(() => { leafletPromise = null; });
  return leafletPromise;
}

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
export const algorithmColor = (index) => cssVar(`--s${(index % 6) + 1}`);

/** "light" or "dark", following the site's theme switch (data-theme) or else the system setting. */
export function currentTheme() {
  const t = document.documentElement.dataset.theme;
  if (t === "light" || t === "dark") return t;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Complete per-algorithm map entry fields (colour, dash, shape) from the algorithm's position in the sorted id list.
 *  The colour is the CSS token itself (var(--sN)), so lines, markers and swatches follow a theme switch without a redraw. */
export function entryStyle(index) {
  const s = algorithmStyle(index);
  return { color: `var(--s${s.colorIndex + 1})`, dash: s.dash, shape: s.shape };
}

/** Small legend glyph: a line sample in the algorithm's colour and dash with its marker shape in the middle. */
export function algorithmSwatch(entry) {
  return svg("svg", { class: "alg-swatch", width: 34, height: 14, viewBox: "0 0 34 14", role: "img",
    "aria-label": `${entry.id || "algorithm"} line style` },
    svg("line", { x1: 1, x2: 33, y1: 7, y2: 7, stroke: entry.color, "stroke-width": 3, "stroke-dasharray": entry.dash || null }),
    marker(entry.shape, 17, 7, entry.color, 3.5));
}

function svg(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  el.append(...kids.flat().filter(Boolean));
  return el;
}

/** One-line key: dot colour = opening time (early to late), filled = visited, hollow = skipped, square = depot. */
export function slotLegend() {
  const cols = slotColors();
  return h("p", { class: "legend", "aria-label": "Map key" },
    h("span", { class: "key" }, "Opens:", " early ", cols.map((c, i) => h("span", { class: "key" }, h("span", { class: "dot filled", style: `background:${c}` }), String(i + 1))), " late"),
    h("span", { class: "key" }, h("span", { class: "dot filled", style: "background:var(--muted)" }), "visited"),
    h("span", { class: "key" }, h("span", { class: "dot hollow" }), "skipped"),
    h("span", { class: "key" }, h("span", { class: "dot hollow faded", style: `opacity:${FADED_OPACITY}` }), "Faded: no shown route goes here"),
    h("span", { class: "key" }, h("span", { class: "dot depot" }), "depot"));
}

/**
 * Geometry shared by both engines. `pos(id)` gives screen x,y; each algorithm gets its own lane (small parallel offset)
 * so shared stretches never hide each other. Returns legs, arrowheads, per-leg shape markers and stop-number badges.
 */
export function routeDrawing(lines, pos, style) {
  const lanes = laneOffsets(lines.length, lines.length > 1 ? 5 : 4);
  const out = { legs: [], arrows: [], shapes: [], badges: [] };
  lines.forEach((line, k) => {
    const s = style(line.entry);
    line.ids.slice(1).forEach((id, i) => {
      const [a, b] = offsetSegment(pos(line.ids[i]), pos(id), lanes[k]);
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      // `line` and `order` say which route this leg belongs to and its place in that route's visiting order (used by the draw-in);
      // `leg` on arrows, shapes and badges points back at the leg they sit on.
      const leg = out.legs.length;
      out.legs.push({ entry: line.entry, from: line.ids[i], to: id, a, b, color: s.color, dash: s.dash, line: k, order: i });
      if (!len) return;
      const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len, angle = Math.atan2(uy, ux) * 180 / Math.PI;
      const at = (t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
      if (len > 26) out.arrows.push({ ...at(0.58), angle, color: s.color, leg });
      if (lines.length > 1 && len > 50) out.shapes.push({ ...at(0.32), shape: s.shape, color: s.color, leg });
      if (i + 1 < line.ids.length - 1) {
        const back = Math.min(13, len * 0.4);
        out.badges.push({ x: b.x - ux * back, y: b.y - uy * back, text: String(i + 1), color: s.color, entry: line.entry, leg });
      }
    });
  });
  return out;
}

/**
 * createRouteMap(instance, { entries, forceSvg, height, summary }) -> { el, ready, setEntries(entries), destroy() }
 * entries = [{ id, label, color, dash, shape, run }]; `color`/`dash` are chosen by the caller (per-algorithm styling).
 * `summary` (default: true when more than one algorithm is shown) adds the compact comparison panel above the map.
 */
export function createRouteMap(instance, opts) {
  let entries = opts.entries;
  let engine = null; // { draw(scene), destroy() }
  // The detail panel is plain text: focused stops and legs are announced through their own accessible names, so it must not be a live
  // region (that would read each one twice). Only an explicit activation (tap, click, Enter, Space) is announced, via `announcer`.
  const detail = h("div", { class: "map-detail" }, "Hover or press a destination for details.");
  const announcer = h("div", { class: "sr-only", role: "status", "aria-live": "polite" });
  const helpId = `map-help-${++mapCount}`;
  const help = h("p", { id: helpId, class: "sr-only" });
  const caption = h("figcaption", { class: "meta map-caption" });
  const stage = h("div", { class: "map-stage", style: opts.height ? `min-height:${opts.height}px` : null });
  const full = h("button", { type: "button", class: "map-full", "aria-pressed": "false", "aria-label": "Fullscreen map", title: "Fullscreen map (Esc to leave)" }, "Fullscreen");
  const note = h("p", { class: "meta map-note", hidden: true });
  const panel = h("div", { class: "map-summary" });
  const tip = h("div", { class: "map-tip", hidden: true, "aria-hidden": "true" });
  // Replay the draw-in (or skip it while it plays). Hidden when motion is off: the map is then always in its final state.
  const replay = h("button", { type: "button", class: "map-btn map-replay", hidden: true });
  const hud = h("div", { class: "map-hud", "aria-hidden": "true", hidden: true });
  const tools = h("div", { class: "map-tools" }, replay, full);
  const frame = h("div", { class: "map-frame" }, stage, tools, hud, tip);
  const el = h("figure", { class: "routemap" }, panel, frame, note, detail, announcer, help, caption);
  const places = instance.locations.filter((l) => !l.isDepot).length;
  const drawCaption = () => { caption.textContent = `Route map: ${entries.map((e) => e.label ?? e.id).join(", ") || "no routes"}, ${places} places.`;
    if (stage.getAttribute("role") === "region") stage.setAttribute("aria-label", caption.textContent.replace(/\.$/, "")); };
  drawCaption();
  // Fullscreen covers the page, so everything outside the map is made inert (no Tab, no screen reader access) while it is on.
  let inerted = [];
  const setInert = (on) => {
    for (const n of inerted) n.inert = false;
    inerted = [];
    if (!on) return;
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      for (const sib of n.parentElement?.children ?? []) if (sib !== n && !["SCRIPT", "LINK", "STYLE"].includes(sib.tagName)) { sib.inert = true; inerted.push(sib); }
    }
  };
  // Fullscreen. Preferred: the browser Fullscreen API on the figure, which puts it in the top layer so no ancestor can clip or
  // re-anchor it. Fallback (iPhone Safari has no element fullscreen, or the request is refused): the CSS-fixed overlay, for which
  // style.css switches off ancestor entrance animations (a transform on an ancestor would make it the containing block).
  const setFullUi = (on) => {
    el.classList.toggle("is-full", on);
    full.setAttribute("aria-pressed", String(on));
    full.textContent = on ? "Exit fullscreen" : "Fullscreen";
    full.setAttribute("aria-label", on ? "Exit fullscreen map" : "Fullscreen map");
    document.documentElement.classList.toggle("map-locked", on);
    setInert(on);
    finishReveal();
    engine?.fullscreen?.(on);
    engine?.invalidate?.();
    if (!on && document.activeElement !== full && !el.contains(document.activeElement)) full.focus();
  };
  const setFull = (on) => {
    if (on === el.classList.contains("is-full")) return;
    setFullUi(on);
    if (on) { if (el.requestFullscreen) { try { Promise.resolve(el.requestFullscreen()).catch(() => {}); } catch { /* CSS overlay stays */ } } }
    else if (document.fullscreenElement === el) document.exitFullscreen().catch(() => {});
  };
  full.addEventListener("click", () => setFull(!el.classList.contains("is-full")));
  const onKey = (e) => { if (e.key === "Escape" && el.classList.contains("is-full")) { setFull(false); full.focus(); } };
  document.addEventListener("keydown", onKey);
  // The browser can leave fullscreen by itself (Esc, a gesture): follow it. Size changes (enter, exit, rotate) refit the map.
  const onFsChange = () => { if (!document.fullscreenElement && el.classList.contains("is-full")) setFullUi(false); engine?.invalidate?.(); };
  document.addEventListener("fullscreenchange", onFsChange);
  const sized = typeof ResizeObserver === "function" ? new ResizeObserver(() => engine?.invalidate?.()) : null;
  sized?.observe(stage);
  let dead = false;

  // What a hover, tap or keyboard focus shows. Times come from the model (stopTimes / legDetails); this only lays them out.
  const byEntry = (id) => entries.find((e) => e.id === id) || { id, label: id };
  const stopParts = (p) => ({ title: `${p.name}${p.depot ? " (depot)" : ""}`, hours: p.depot ? null : `Open ${p.window}${p.slot == null ? "" : ` (slot ${p.slot + 1} of 4)`}`,
    rows: entries.map((e) => ({ entry: e, text: stopLine(stopTimes(e.run, instance, p.id)) })) });
  const legParts = (l) => {
    const e = byEntry(l.entry), g = legDetails(e.run, instance, l.from, l.to);
    return g && { title: `${g.from} to ${g.to}`, hours: null, rows: [{ entry: e, text: null }], facts: legRows(g) };
  };
  const plain = (parts) => [parts.title, parts.hours, ...parts.rows.map((r) => r.text == null ? r.entry.label ?? r.entry.id : `${r.entry.label ?? r.entry.id}: ${r.text}`),
    ...(parts.facts || []).map(([k, v]) => `${k} ${v}`)].filter(Boolean).join(". ");
  const unvisited = (p) => !p.depot && !p.filled && entries.length > 0; // drawn faded: no shown route goes here
  const stopLabel = (p) => plain(stopParts(p)) + (unvisited(p) ? ". Not visited by any shown route" : "");
  const legLabel = (l) => { const parts = legParts(l); return parts ? plain(parts) : ""; };
  function render(into, parts) {
    into.replaceChildren(...[h("strong", { class: "tip-title" }, parts.title), parts.hours ? h("div", { class: "tip-hours" }, parts.hours) : null,
      ...parts.rows.map((r) => h("div", { class: "tip-row" }, algorithmSwatch(r.entry), h("strong", {}, r.entry.label ?? r.entry.id), r.text == null ? null : h("span", { class: "tip-text" }, r.text))),
      parts.facts ? h("dl", { class: "tip-facts" }, parts.facts.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null].filter(Boolean));
  }
  function place(ev) {
    const fr = frame.getBoundingClientRect(), w = tip.offsetWidth, ht = tip.offsetHeight, gapPx = 16;
    let x = ev.clientX - fr.left + gapPx, y = ev.clientY - fr.top + gapPx;
    if (x + w > fr.width - 4) x = ev.clientX - fr.left - w - gapPx;
    if (y + ht > fr.height - 4) y = ev.clientY - fr.top - ht - gapPx;
    tip.style.left = `${Math.max(4, Math.min(x, fr.width - w - 4))}px`;
    tip.style.top = `${Math.max(4, Math.min(y, fr.height - ht - 4))}px`;
  }
  const open = (parts, ev, announce) => {
    render(detail, parts); render(tip, parts); tip.hidden = false; place(ev);
    if (announce) announcer.textContent = plain(parts);
  };
  const hover = {
    stop: (p, ev, announce) => open(stopParts(p), ev, announce),
    leg: (l, ev, announce) => { const parts = legParts(l); if (parts) open(parts, ev, announce); },
    move: (ev) => { if (!tip.hidden) place(ev); },
    hide: () => { tip.hidden = true; },
    stopLabel, legLabel, unvisited,
  };
  const onEsc = (e) => { if (e.key === "Escape") hover.hide(); };
  document.addEventListener("keydown", onEsc);
  const scene = () => buildScene(instance, entries);
  const style = (id) => entries.find((e) => e.id === id) || {};

  function drawPanel() {
    const wanted = opts.summary ?? entries.length > 1;
    panel.hidden = !wanted;
    if (!wanted) { panel.replaceChildren(); return; }
    const rows = summaryRows(entries);
    const byId = new Map(entries.map((e) => [e.id, e]));
    const notes = differenceNotes(instance, entries);
    panel.replaceChildren(
      h("ul", { class: "sum-list", "aria-label": "Comparison" }, rows.map((r) => h("li", { class: r.best ? "best" : null },
        algorithmSwatch(byId.get(r.id)), h("strong", {}, r.label),
        r.valid ? h("span", { class: "sum-nums" }, `${r.visited} places, ${r.distance}, ${r.time}`)
          : h("span", { class: "sum-nums" }, "no valid answer"),
        r.best ? h("span", { class: "badge ok" }, "Best") : null))),
      ...(notes.length ? [h("ul", { class: "sum-notes" }, notes.map((n) => h("li", {}, n)))] : []));
  }

  // ---- draw-in: each route draws itself leg by leg in visiting order, stops light up as they are reached, stop numbers pop in.
  // The map is drawn complete first; the reveal resets it and plays only once the map is on screen, and any interruption
  // (zoom, pan, resize, Skip, motion turned off) jumps straight to the complete drawing.
  let rv = null;
  const replayText = () => (entries.length > 1 ? "Replay routes" : "Replay route");
  function paintReplay() {
    const can = motionOn() && !!engine?.anim?.legs.length;
    replay.hidden = !can;
    replay.textContent = rv ? "Skip animation" : replayText();
    replay.classList.toggle("playing", !!rv);
    replay.setAttribute("aria-label", rv ? "Skip the route animation" : `${replayText()} in visiting order`);
  }
  function finishReveal() {
    if (!rv) return;
    cancelAnimationFrame(rv.raf);
    rv.finish();
    rv = null;
    hud.hidden = true;
    paintReplay();
  }
  function startReveal() {
    finishReveal();
    const a = engine?.anim;
    if (!motionOn() || !a || !a.legs.length) return;
    const perLine = new Map();
    a.legs.forEach((l) => perLine.set(l.line, (perLine.get(l.line) || 0) + 1));
    const plans = new Map([...perLine].map(([k, n]) => [k, revealSchedule(n, { budgetMs: Math.min(3200, 900 + n * 160), maxLegMs: 420, minLegMs: 40 })]));
    const timing = a.legs.map((l) => plans.get(l.line)[l.order]);
    const total = Math.max(...timing.map((t) => t.start + t.duration));
    const stopsTotal = a.legs.filter((l) => l.line === 0 && a.stops.has(l.to)).length;
    const done = new Array(a.legs.length).fill(false);
    let reached = 0;
    a.legs.forEach((l) => l.set(0));
    a.pops.forEach((p) => p.node.classList.add("rv-wait"));
    for (const nodes of a.stops.values()) nodes.forEach((n) => n.classList.add("rv-dim"));
    frame.classList.remove("beacon-go"); void frame.offsetWidth; frame.classList.add("beacon-go");
    a.heads?.forEach((hd) => hd.show(true));
    hud.hidden = false;
    const finish = () => {
      a.legs.forEach((l) => l.set(1));
      a.pops.forEach((p) => p.node.classList.remove("rv-wait", "rv-pop"));
      for (const nodes of a.stops.values()) nodes.forEach((n) => n.classList.remove("rv-dim", "rv-lit"));
      a.heads?.forEach((hd) => hd.show(false));
    };
    const t0 = performance.now();
    const tick = (now) => {
      const t = now - t0;
      a.legs.forEach((l, i) => {
        if (done[i]) return;
        const { start, duration } = timing[i];
        if (t < start) return;
        const p = Math.min(1, (t - start) / duration);
        l.set(p);
        a.heads?.[l.line]?.at(l, p);
        if (p < 1) return;
        done[i] = true;
        a.pops.forEach((q) => { if (q.leg === i) { q.node.classList.remove("rv-wait"); q.node.classList.add("rv-pop"); } });
        a.stops.get(l.to)?.forEach((n) => { if (n.classList.contains("rv-dim")) { n.classList.remove("rv-dim"); n.classList.add("rv-lit"); } });
        if (l.line === 0 && a.stops.has(l.to)) reached++;
      });
      hud.textContent = entries.length > 1 ? `Drawing ${entries.length} routes in visiting order` : `Visiting order: stop ${Math.min(reached, stopsTotal)} of ${stopsTotal}`;
      if (t >= total) { finishReveal(); return; }
      rv.raf = requestAnimationFrame(tick);
    };
    rv = { finish, raf: requestAnimationFrame(tick) };
    paintReplay();
  }
  replay.addEventListener("click", () => (rv ? finishReveal() : startReveal()));
  const onMotion = () => { if (!motionOn()) finishReveal(); paintReplay(); };
  window.addEventListener("motionchange", onMotion);
  let seen = null; // plays the first time the map is at least a third on screen
  const watch = () => {
    if (opts.animate === false || !motionOn() || typeof IntersectionObserver !== "function") return;
    seen = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { seen.disconnect(); seen = null; startReveal(); } }, { threshold: 0.35 });
    seen.observe(stage);
  };
  const hooks = { interrupt: finishReveal };

  const ready = chooseEngine(loadLeaflet, 4000, opts.forceSvg).then((name) => {
    if (dead) return;
    engine = name === "leaflet" ? leafletEngine(stage, hover, style, hooks) : svgEngine(stage, hover, style);
    el.dataset.engine = name;
    const target = name === "leaflet" ? stage : stage.firstElementChild;
    target.setAttribute("aria-describedby", helpId);
    if (name === "leaflet") { stage.setAttribute("role", "region"); drawCaption(); }
    help.textContent = name === "leaflet"
      ? "Map. Arrow keys pan, plus and minus zoom. Tab moves through the routes and the stops. Press Enter or Space on a stop or route for its details, and Escape to close them."
      : "Map drawing. Tab moves through the routes and the stops. Press Enter or Space on a stop or route for its details, and Escape to close them.";
    if (name === "svg") {
      note.hidden = false;
      note.textContent = opts.forceSvg ? "Plain map (forced)." : "Map tiles unavailable here, so this is a plain drawing of the same destinations and routes.";
    }
    engine.draw(scene());
    paintReplay();
    watch();
  });
  drawPanel();

  return {
    el,
    ready,
    setEntries(next) { finishReveal(); entries = next; drawPanel(); drawCaption(); if (engine) engine.draw(scene()); paintReplay(); },
    replay: () => startReveal(),
    destroy() { dead = true; finishReveal(); seen?.disconnect(); window.removeEventListener("motionchange", onMotion); setInert(false); document.removeEventListener("keydown", onKey); document.removeEventListener("keydown", onEsc); document.removeEventListener("fullscreenchange", onFsChange); sized?.disconnect(); if (document.fullscreenElement === el) document.exitFullscreen().catch(() => {}); document.documentElement.classList.remove("map-locked"); engine?.destroy(); },
  };
}

/** Centre of an element on screen, in the same shape as a mouse event position (for keyboard focus). */
const centreOf = (node) => { const r = node.getBoundingClientRect(); return { clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 }; };
const dotClass = (p) => (p.depot ? "depot" : p.filled ? "filled" : "hollow");

function arrowPath(x, y, angle, color) {
  return svg("path", { d: "M-5,-4.5 L5,0 L-5,4.5 Z", transform: `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${angle.toFixed(1)})`,
    fill: color, stroke: "var(--surface)", "stroke-width": 1, "stroke-linejoin": "round", class: "arrow", "aria-hidden": "true" });
}

function badgeNode(x, y, text, color) {
  return svg("g", { class: "badge-g rv-item", "aria-hidden": "true" },
    svg("circle", { cx: x, cy: y, r: 8, fill: "var(--surface)", stroke: color, "stroke-width": 2 }),
    svg("text", { x, y: y + 3.5, "text-anchor": "middle", class: "badge-t" }, text));
}

/** A leg drawn from a towards b, `p` of the way (0..1). */
const lerp = (a, b, p) => ({ x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p });

function svgEngine(stage, hover, style) {
  const W = 640, H = 480;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "map-svg", preserveAspectRatio: "xMidYMid meet", role: "group", "aria-label": "Route map (plain drawing)" });
  stage.replaceChildren(root);
  root.addEventListener("click", (e) => { if (e.target === root) hover.hide(); });
  const colors = slotColors();
  const api = {
    anim: null,
    draw(scene) {
      const xy = project(scene.points, W, H, 44);
      const pos = new Map(scene.points.map((p, i) => [p.id, xy[i]]));
      const g = routeDrawing(scene.lines, (id) => pos.get(id), style);
      root.replaceChildren(svg("rect", { class: "map-grid", x: 0, y: 0, width: W, height: H, fill: "url(#map-grid-" + gridId + ")", "aria-hidden": "true" }),
        svg("defs", {}, svg("pattern", { id: "map-grid-" + gridId, width: 40, height: 40, patternUnits: "userSpaceOnUse" },
          svg("path", { d: "M40 0H0V40", fill: "none", class: "map-grid-line" }))));
      const halos = g.legs.map((l) => root.appendChild(svg("line", { class: "route-halo", stroke: "var(--surface)", "stroke-width": 7, "stroke-linecap": "round", opacity: 0.8,
        x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) })));
      const lines = [];
      for (const l of g.legs) {
        const line = svg("line", { class: "route", stroke: l.color, style: `color:${l.color}`, "stroke-width": 3.5, "stroke-dasharray": l.dash || null,
          "stroke-linecap": "round", opacity: 0.92, x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) });
        lines.push(line);
        root.append(line);
      }
      const pops = [];
      g.shapes.forEach((s) => pops.push({ leg: s.leg, node: root.appendChild(svg("g", { class: "rv-item" }, marker(s.shape, s.x, s.y, s.color, 3.5))) }));
      g.arrows.forEach((a) => pops.push({ leg: a.leg, node: root.appendChild(svg("g", { class: "rv-item" }, arrowPath(a.x, a.y, a.angle, a.color))) }));
      // Wide invisible lines on top, so thin routes are easy to hover, tap or focus.
      const hitWidth = scene.lines.length > 1 ? 11 : 18;
      g.legs.forEach((l, i) => {
        const hit = svg("line", { class: "leg-hit", tabindex: 0, role: "button", "aria-label": hover.legLabel(l), stroke: "transparent", "stroke-width": hitWidth,
          "stroke-linecap": "round", x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) });
        const lit = (on) => lines[i].setAttribute("stroke-width", on ? 6.5 : 3.5);
        const enter = (ev, announce) => { lit(true); hover.leg(l, ev, announce); };
        hit.addEventListener("mouseenter", enter);
        hit.addEventListener("mousemove", (ev) => hover.move(ev));
        hit.addEventListener("mouseleave", () => { lit(false); hover.hide(); });
        hit.addEventListener("click", (ev) => enter(ev, true));
        hit.addEventListener("focus", () => { lit(true); hover.leg(l, centreOf(hit)); });
        hit.addEventListener("blur", () => { lit(false); hover.hide(); });
        hit.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); enter(centreOf(hit), true); } });
        root.append(hit);
      });
      const plan = new Set(labelPlan(scene.points.map((p, i) => ({ id: p.id, name: p.name, ...xy[i], visited: p.filled })), W, H));
      const stops = new Map();
      for (const p of scene.points) {
        const { x, y } = pos.get(p.id);
        const label = hover.stopLabel(p);
        const mark = p.depot
          ? svg("rect", { x: x - 8, y: y - 8, width: 16, height: 16, class: "pt depot" })
          : svg("circle", { cx: x, cy: y, r: p.filled ? 7 : 6, class: `pt ${dotClass(p)}`, fill: p.filled ? colors[p.slot] : "var(--surface)",
            stroke: p.filled ? "var(--text)" : colors[p.slot], "stroke-width": p.filled ? 1.5 : 3 });
        const faded = hover.unvisited(p);
        const ring = !p.depot && !p.filled ? svg("circle", { cx: x, cy: y, r: 8.5, fill: "none", stroke: faded ? "var(--text)" : "var(--muted)", "stroke-width": faded ? 1.5 : 1.2 }) : null;
        const side = labelSide({ name: p.name, x }, W);
        const text = p.depot || plan.has(p.id)
          ? svg("text", { x: side === "right" ? x + 11 : x - 11, y: y + 4, class: "pt-label", "text-anchor": side === "right" ? "start" : "end" }, p.name) : null;
        if (faded) for (const part of [ring, mark]) part?.setAttribute("opacity", FADED_OPACITY); // the name stays full strength so it remains readable
        // The depot sends out a soft beacon pulse while the routes draw (two pulses, then still).
        const beacon = p.depot ? svg("g", { class: "beacon-rings", "aria-hidden": "true" },
          svg("circle", { class: "beacon-ring", cx: x, cy: y, r: 10 }), svg("circle", { class: "beacon-ring late", cx: x, cy: y, r: 10 })) : null;
        const grp = svg("g", { tabindex: 0, role: "button", "aria-label": label, class: faded ? "pt-group faded" : "pt-group" }, beacon, ring, mark, text);
        if (p.filled && !p.depot) stops.set(p.id, [mark]);
        grp.addEventListener("click", (ev) => hover.stop(p, ev, true));
        grp.addEventListener("mouseenter", (ev) => hover.stop(p, ev));
        grp.addEventListener("mousemove", (ev) => hover.move(ev));
        grp.addEventListener("mouseleave", () => hover.hide());
        grp.addEventListener("focus", () => hover.stop(p, centreOf(grp)));
        grp.addEventListener("blur", () => hover.hide());
        grp.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hover.stop(p, centreOf(grp), true); } });
        root.append(grp);
      }
      g.badges.forEach((b) => pops.push({ leg: b.leg, node: root.appendChild(badgeNode(b.x, b.y, b.text, b.color)) }));
      // The glowing head that travels along each route while it draws.
      const heads = scene.lines.map((line) => {
        const dot = root.appendChild(svg("circle", { class: "rv-head", r: 5, fill: style(line.entry).color, style: `color:${style(line.entry).color}`, visibility: "hidden", "aria-hidden": "true" }));
        return { show: (on) => dot.setAttribute("visibility", on ? "visible" : "hidden"),
          at: (l, p) => { const q = lerp(l.a, l.b, p); dot.setAttribute("cx", q.x.toFixed(1)); dot.setAttribute("cy", q.y.toFixed(1)); } };
      });
      api.anim = {
        legs: g.legs.map((l, i) => ({ line: l.line, order: l.order, to: l.to, a: l.a, b: l.b,
          set: (p) => { const q = lerp(l.a, l.b, p); for (const n of [halos[i], lines[i]]) { n.setAttribute("x2", q.x.toFixed(1)); n.setAttribute("y2", q.y.toFixed(1)); } } })),
        pops, stops, heads,
      };
    },
    destroy() { root.remove(); },
  };
  const gridId = ++mapCount;
  return api;
}

function leafletEngine(stage, hover, style, hooks) {
  const L = window.L;
  const map = L.map(stage, { zoomControl: true, attributionControl: true, keyboard: true, scrollWheelZoom: false,
    minZoom: TILE_LIMITS.minZoom, maxZoom: TILE_LIMITS.maxZoom });
  // Wheel zoom only after a click, so scrolling the page past a map never zooms it by accident.
  map.on("click focus", () => map.scrollWheelZoom.enable());
  map.on("mouseout blur", () => map.scrollWheelZoom.disable());
  // On a touch screen a one-finger drag would otherwise pan the map instead of scrolling the page (the map is most of a screen tall).
  // The page scrolls natively over it (touch-action stays pan-y); pinch still zooms, and fullscreen turns one-finger panning on.
  const coarse = typeof matchMedia === "function" && matchMedia("(pointer: coarse)").matches;
  if (coarse) map.dragging.disable();
  // Real tiles end at maxNativeZoom; deeper zooms upscale them (soft but never blank). A missing tile shows the background.
  L.tileLayer(TILES, { minZoom: TILE_LIMITS.minZoom, maxZoom: TILE_LIMITS.maxZoom, maxNativeZoom: TILE_LIMITS.maxNativeZoom,
    errorTileUrl: BLANK_TILE, className: "base-tiles", attribution: ATTRIBUTION }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  const colors = slotColors();
  let fitted = false, last = null, fitZoom = null;
  const api = { anim: null };

  function paint(scene) {
    layer.clearLayers();
    const ll = new Map(scene.points.map((p) => [p.id, L.latLng(p.lat, p.lon)]));
    const px = new Map([...ll].map(([id, v]) => [id, map.latLngToContainerPoint(v)]));
    const back = (p) => map.containerPointToLatLng([p.x, p.y]);
    const g = routeDrawing(scene.lines, (id) => px.get(id), style);
    const halos = g.legs.map((l) => L.polyline([back(l.a), back(l.b)], { color: "var(--surface)", weight: 8, opacity: 0.8, lineCap: "round", lineJoin: "round", interactive: false, className: "route-halo" }).addTo(layer));
    const lines = g.legs.map((l) => {
      const pl = L.polyline([back(l.a), back(l.b)], { color: l.color, weight: 4.5, opacity: 0.96, lineCap: "round", lineJoin: "round", dashArray: l.dash || null, interactive: false, className: "route" }).addTo(layer);
      pl.getElement()?.style.setProperty("color", l.color); // the glow (map.css) takes the route's own colour
      return pl;
    });
    // Wide invisible lines on top, so thin routes are easy to hover, tap or focus.
    const hitWeight = scene.lines.length > 1 ? 12 : 20;
    g.legs.forEach((l, i) => {
      const hit = L.polyline([back(l.a), back(l.b)], { color: "#000", weight: hitWeight, opacity: 0, lineCap: "round", className: "leg-hit", bubblingMouseEvents: false }).addTo(layer);
      const lit = (on) => lines[i].setStyle({ weight: on ? 7.5 : 4.5, opacity: on ? 1 : 0.96 });
      hit.on("mouseover", (e) => { lit(true); hover.leg(l, e.originalEvent); });
      hit.on("click", (e) => { lit(true); hover.leg(l, e.originalEvent, true); });
      hit.on("mousemove", (e) => hover.move(e.originalEvent));
      hit.on("mouseout", () => { lit(false); hover.hide(); });
      const wire = () => {
        const node = hit.getElement();
        if (!node) return;
        node.setAttribute("tabindex", "0"); node.setAttribute("role", "button"); node.setAttribute("aria-label", hover.legLabel(l));
        node.addEventListener("focus", () => { lit(true); hover.leg(l, centreOf(node)); });
        node.addEventListener("blur", () => { lit(false); hover.hide(); });
        node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hover.leg(l, centreOf(node), true); } });
      };
      hit.on("add", wire); wire();
    });
    const icon = (node, size, cls = "lf-icon") => L.divIcon({ html: node, className: cls, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
    const pops = [];
    for (const s of g.shapes) {
      const glyph = svg("svg", { width: 12, height: 12, viewBox: "0 0 12 12", class: "rv-item" }, marker(s.shape, 6, 6, s.color, 3.5));
      L.marker(back(s), { interactive: false, keyboard: false, icon: icon(glyph, 12) }).addTo(layer);
      pops.push({ leg: s.leg, node: glyph });
    }
    for (const a of g.arrows) {
      const glyph = svg("svg", { width: 14, height: 14, viewBox: "-7 -7 14 14", class: "rv-item" }, arrowPath(0, 0, a.angle, a.color));
      L.marker(back(a), { interactive: false, keyboard: false, icon: icon(glyph, 14) }).addTo(layer);
      pops.push({ leg: a.leg, node: glyph });
    }
    for (const b of g.badges) {
      const badge = h("span", { class: "lf-badge rv-item", style: `--ring:${b.color}` }, b.text);
      L.marker(back(b), { interactive: false, keyboard: false, icon: icon(badge, 16) }).addTo(layer);
      pops.push({ leg: b.leg, node: badge });
    }
    const size = map.getSize();
    const plan = new Set(labelPlan(scene.points.map((p) => ({ id: p.id, name: p.name, ...px.get(p.id), visited: p.filled })), size.x, size.y));
    // Names are drawn only once zoomed in past the initial fit (the depot keeps its name as a landmark); hover, tap and focus always give the name.
    const showNames = labelsVisible(map.getZoom(), fitZoom ?? map.getZoom(), TILE_LIMITS.maxZoom);
    const stops = new Map();
    for (const p of scene.points) {
      const faded = hover.unvisited(p);
      const dot = h("span", { class: `lf-dot ${dotClass(p)}${faded ? " faded" : ""}`, style: p.depot ? null : `--slot:${colors[p.slot]}${faded ? `;opacity:${FADED_OPACITY}` : ""}` });
      if (p.filled && !p.depot) stops.set(p.id, [dot]);
      const m = L.marker(ll.get(p.id), { icon: icon(dot, 20), keyboard: true, zIndexOffset: 500 }).addTo(layer);
      const side = labelSide({ name: p.name, x: px.get(p.id).x }, size.x);
      if (p.depot || (showNames && plan.has(p.id))) m.bindTooltip(p.name, { permanent: true, direction: side, offset: [side === "right" ? 6 : -6, 0], className: "lf-label" });
      m.on("mouseover", (e) => hover.stop(p, e.originalEvent));
      m.on("click", (e) => { if (e.originalEvent?.detail !== 0) hover.stop(p, e.originalEvent, true); }); // keyboard Enter is handled below
      m.on("mousemove", (e) => hover.move(e.originalEvent));
      m.on("mouseout", () => hover.hide());
      const wire = () => {
        const mel = m.getElement();
        if (!mel) return;
        mel.setAttribute("aria-label", hover.stopLabel(p)); mel.setAttribute("role", "button");
        mel.addEventListener("focus", () => hover.stop(p, centreOf(mel)));
        mel.addEventListener("blur", () => hover.hide());
        // Leaflet itself turns only Enter into a click; handle Enter and Space here so details show (again) after Escape too.
        mel.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); hover.stop(p, centreOf(mel), true); } });
      };
      m.on("add", wire); wire();
    }
    // The glowing head that travels along each route while it draws.
    const heads = scene.lines.map((line) => {
      const c = style(line.entry).color;
      const dot = L.circleMarker(back(g.legs[0]?.a ?? { x: 0, y: 0 }), { radius: 5, color: c, fillColor: c, fillOpacity: 1, weight: 0, interactive: false, className: "rv-head" });
      return { show: (on) => (on ? dot.addTo(layer) : dot.remove()), at: (l, p) => dot.setLatLng(back(lerp(l.a, l.b, p))) };
    });
    api.anim = {
      legs: g.legs.map((l, i) => ({ line: l.line, order: l.order, to: l.to, a: l.a, b: l.b,
        set: (p) => { const ends = [back(l.a), back(lerp(l.a, l.b, p))]; halos[i].setLatLngs(ends); lines[i].setLatLngs(ends); } })),
      pops, stops, heads,
    };
  }
  const repaint = () => { if (last) paint(last); };
  // Zooming or panning mid draw-in jumps to the complete drawing, then repaints for the new view.
  map.on("zoomstart movestart", () => hooks?.interrupt());
  map.on("zoomend moveend resize", () => { hooks?.interrupt(); hover.hide(); repaint(); });
  map.on("click", () => hover.hide());
  return Object.assign(api, {
    draw(scene) {
      last = scene;
      if (!fitted) { map.fitBounds(L.latLngBounds(scene.points.map((p) => [p.lat, p.lon])), { padding: [40, 40] }); fitted = true; fitZoom = map.getZoom(); }
      paint(scene);
    },
    invalidate() { map.invalidateSize(); },
    fullscreen(on) { if (coarse) (on ? map.dragging.enable() : map.dragging.disable()); map.invalidateSize(); },
    destroy() { map.off(); map.remove(); },
  });
}
