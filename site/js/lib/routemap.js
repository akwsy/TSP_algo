// Interactive route map. Leaflet (pinned, from cdnjs) on label-free tiles when it loads in time, otherwise a plain projected
// SVG drawing of the same scene, so the map never goes blank. Force the fallback with ?map=svg on the page URL.
// The only text on the map is the destination names. Every route is a straight-line path with arrowheads and stop numbers.
import { h } from "./dom.js";
import { buildScene, chooseEngine, project, slotColors, laneOffsets, offsetSegment, summaryRows, differenceNotes, labelPlan, labelSide, TILE_LIMITS, stopTimes, stopLine, legDetails, legRows } from "./mapmodel.js";
import { algorithmStyle } from "./algstyle.js";
import { marker } from "./charts.js";

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

/** Complete per-algorithm map entry fields (colour, dash, shape) from the algorithm's position in the sorted id list. */
export function entryStyle(index) {
  const s = algorithmStyle(index);
  return { color: algorithmColor(s.colorIndex), dash: s.dash, shape: s.shape };
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
    h("span", { class: "key" }, "Opens:", " early ", cols.map((c) => h("span", { class: "dot filled", style: `background:${c}` })), " late"),
    h("span", { class: "key" }, h("span", { class: "dot filled", style: "background:var(--muted)" }), "visited"),
    h("span", { class: "key" }, h("span", { class: "dot hollow" }), "skipped"),
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
      out.legs.push({ entry: line.entry, from: line.ids[i], to: id, a, b, color: s.color, dash: s.dash });
      if (!len) return;
      const ux = (b.x - a.x) / len, uy = (b.y - a.y) / len, angle = Math.atan2(uy, ux) * 180 / Math.PI;
      const at = (t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
      if (len > 26) out.arrows.push({ ...at(0.58), angle, color: s.color });
      if (lines.length > 1 && len > 50) out.shapes.push({ ...at(0.32), shape: s.shape, color: s.color });
      if (i + 1 < line.ids.length - 1) {
        const back = Math.min(13, len * 0.4);
        out.badges.push({ x: b.x - ux * back, y: b.y - uy * back, text: String(i + 1), color: s.color, entry: line.entry });
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
  const detail = h("div", { class: "map-detail", role: "status", "aria-live": "polite" }, "Hover or press a destination for details.");
  const stage = h("div", { class: "map-stage", style: opts.height ? `min-height:${opts.height}px` : null });
  const full = h("button", { type: "button", class: "map-full", "aria-pressed": "false", "aria-label": "Fullscreen map", title: "Fullscreen map (Esc to leave)" }, "Fullscreen");
  const note = h("p", { class: "meta map-note", hidden: true });
  const panel = h("div", { class: "map-summary" });
  const tip = h("div", { class: "map-tip", hidden: true, "aria-hidden": "true" });
  const frame = h("div", { class: "map-frame" }, stage, full, tip);
  const el = h("figure", { class: "routemap" }, panel, frame, note, detail);
  const setFull = (on) => {
    el.classList.toggle("is-full", on);
    full.setAttribute("aria-pressed", String(on));
    full.textContent = on ? "Exit fullscreen" : "Fullscreen";
    full.setAttribute("aria-label", on ? "Exit fullscreen map" : "Fullscreen map");
    document.documentElement.classList.toggle("map-locked", on);
    engine?.invalidate?.();
  };
  full.addEventListener("click", () => setFull(!el.classList.contains("is-full")));
  const onKey = (e) => { if (e.key === "Escape" && el.classList.contains("is-full")) { setFull(false); full.focus(); } };
  document.addEventListener("keydown", onKey);
  let dead = false;

  // What a hover, tap or keyboard focus shows. Times come from the model (stopTimes / legDetails); this only lays them out.
  const byEntry = (id) => entries.find((e) => e.id === id) || { id, label: id };
  const stopParts = (p) => ({ title: `${p.name}${p.depot ? " (depot)" : ""}`, hours: p.depot ? null : `Open ${p.window}`,
    rows: entries.map((e) => ({ entry: e, text: stopLine(stopTimes(e.run, instance, p.id)) })) });
  const legParts = (l) => {
    const e = byEntry(l.entry), g = legDetails(e.run, instance, l.from, l.to);
    return g && { title: `${g.from} to ${g.to}`, hours: null, rows: [{ entry: e, text: null }], facts: legRows(g) };
  };
  const plain = (parts) => [parts.title, parts.hours, ...parts.rows.map((r) => r.text == null ? r.entry.label ?? r.entry.id : `${r.entry.label ?? r.entry.id}: ${r.text}`),
    ...(parts.facts || []).map(([k, v]) => `${k} ${v}`)].filter(Boolean).join(". ");
  const stopLabel = (p) => plain(stopParts(p));
  const legLabel = (l) => { const parts = legParts(l); return parts ? plain(parts) : ""; };
  function render(into, parts) {
    into.replaceChildren(h("strong", { class: "tip-title" }, parts.title), parts.hours ? h("div", { class: "tip-hours" }, parts.hours) : null,
      ...parts.rows.map((r) => h("div", { class: "tip-row" }, algorithmSwatch(r.entry), h("strong", {}, r.entry.label ?? r.entry.id), r.text == null ? null : h("span", { class: "tip-text" }, r.text))),
      parts.facts ? h("dl", { class: "tip-facts" }, parts.facts.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null);
  }
  function place(ev) {
    const fr = frame.getBoundingClientRect(), w = tip.offsetWidth, ht = tip.offsetHeight, gapPx = 16;
    let x = ev.clientX - fr.left + gapPx, y = ev.clientY - fr.top + gapPx;
    if (x + w > fr.width - 4) x = ev.clientX - fr.left - w - gapPx;
    if (y + ht > fr.height - 4) y = ev.clientY - fr.top - ht - gapPx;
    tip.style.left = `${Math.max(4, Math.min(x, fr.width - w - 4))}px`;
    tip.style.top = `${Math.max(4, Math.min(y, fr.height - ht - 4))}px`;
  }
  const open = (parts, ev) => { render(detail, parts); render(tip, parts); tip.hidden = false; place(ev); };
  const hover = {
    stop: (p, ev) => open(stopParts(p), ev),
    leg: (l, ev) => { const parts = legParts(l); if (parts) open(parts, ev); },
    move: (ev) => { if (!tip.hidden) place(ev); },
    hide: () => { tip.hidden = true; },
    stopLabel, legLabel,
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

  const ready = chooseEngine(loadLeaflet, 4000, opts.forceSvg).then((name) => {
    if (dead) return;
    engine = name === "leaflet" ? leafletEngine(stage, hover, style) : svgEngine(stage, hover, style);
    el.dataset.engine = name;
    if (name === "svg") {
      note.hidden = false;
      note.textContent = opts.forceSvg ? "Plain map (forced)." : "Map tiles unavailable here, so this is a plain drawing of the same destinations and routes.";
    }
    engine.draw(scene());
  });
  drawPanel();

  return {
    el,
    ready,
    setEntries(next) { entries = next; drawPanel(); if (engine) engine.draw(scene()); },
    destroy() { dead = true; document.removeEventListener("keydown", onKey); document.removeEventListener("keydown", onEsc); document.documentElement.classList.remove("map-locked"); engine?.destroy(); },
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
  return svg("g", { class: "badge-g", "aria-hidden": "true" },
    svg("circle", { cx: x, cy: y, r: 7.5, fill: color, stroke: "var(--surface)", "stroke-width": 1.5 }),
    svg("text", { x, y: y + 3.5, "text-anchor": "middle", class: "badge-t" }, text));
}

function svgEngine(stage, hover, style) {
  const W = 640, H = 480;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "map-svg", preserveAspectRatio: "xMidYMid meet", role: "group", "aria-label": "Route map (plain drawing)" });
  stage.replaceChildren(root);
  root.addEventListener("click", (e) => { if (e.target === root) hover.hide(); });
  const colors = slotColors();
  return {
    draw(scene) {
      const xy = project(scene.points, W, H, 44);
      const pos = new Map(scene.points.map((p, i) => [p.id, xy[i]]));
      const g = routeDrawing(scene.lines, (id) => pos.get(id), style);
      root.replaceChildren();
      for (const l of g.legs) {
        root.append(svg("line", { class: "route-halo", stroke: "var(--surface)", "stroke-width": 7, "stroke-linecap": "round", opacity: 0.8,
          x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) }));
      }
      const lines = [];
      for (const l of g.legs) {
        const line = svg("line", { class: "route", stroke: l.color, "stroke-width": 3.5, "stroke-dasharray": l.dash || null,
          "stroke-linecap": "round", opacity: 0.92, x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) });
        lines.push(line);
        root.append(line);
      }
      g.shapes.forEach((s) => root.append(marker(s.shape, s.x, s.y, s.color, 3.5)));
      g.arrows.forEach((a) => root.append(arrowPath(a.x, a.y, a.angle, a.color)));
      // Wide invisible lines on top, so thin routes are easy to hover, tap or focus.
      const hitWidth = scene.lines.length > 1 ? 11 : 18;
      g.legs.forEach((l, i) => {
        const hit = svg("line", { class: "leg-hit", tabindex: 0, role: "button", "aria-label": hover.legLabel(l), stroke: "transparent", "stroke-width": hitWidth,
          "stroke-linecap": "round", x1: l.a.x.toFixed(1), y1: l.a.y.toFixed(1), x2: l.b.x.toFixed(1), y2: l.b.y.toFixed(1) });
        const lit = (on) => lines[i].setAttribute("stroke-width", on ? 6.5 : 3.5);
        const enter = (ev) => { lit(true); hover.leg(l, ev); };
        hit.addEventListener("mouseenter", enter);
        hit.addEventListener("mousemove", (ev) => hover.move(ev));
        hit.addEventListener("mouseleave", () => { lit(false); hover.hide(); });
        hit.addEventListener("click", enter);
        hit.addEventListener("focus", () => { lit(true); hover.leg(l, centreOf(hit)); });
        hit.addEventListener("blur", () => { lit(false); hover.hide(); });
        hit.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); enter(centreOf(hit)); } });
        root.append(hit);
      });
      const plan = new Set(labelPlan(scene.points.map((p, i) => ({ id: p.id, name: p.name, ...xy[i], visited: p.filled })), W, H));
      for (const p of scene.points) {
        const { x, y } = pos.get(p.id);
        const label = hover.stopLabel(p);
        const mark = p.depot
          ? svg("rect", { x: x - 8, y: y - 8, width: 16, height: 16, class: "pt depot" })
          : svg("circle", { cx: x, cy: y, r: p.filled ? 7 : 6, class: `pt ${dotClass(p)}`, fill: p.filled ? colors[p.slot] : "var(--surface)",
            stroke: p.filled ? "var(--text)" : colors[p.slot], "stroke-width": p.filled ? 1.5 : 3 });
        const ring = !p.depot && !p.filled ? svg("circle", { cx: x, cy: y, r: 8.5, fill: "none", stroke: "var(--muted)", "stroke-width": 1.2 }) : null;
        const side = labelSide({ name: p.name, x }, W);
        const text = p.depot || plan.has(p.id)
          ? svg("text", { x: side === "right" ? x + 11 : x - 11, y: y + 4, class: "pt-label", "text-anchor": side === "right" ? "start" : "end" }, p.name) : null;
        const grp = svg("g", { tabindex: 0, role: "button", "aria-label": label, class: "pt-group" }, ring, mark, text);
        grp.addEventListener("click", (ev) => hover.stop(p, ev));
        grp.addEventListener("mouseenter", (ev) => hover.stop(p, ev));
        grp.addEventListener("mousemove", (ev) => hover.move(ev));
        grp.addEventListener("mouseleave", () => hover.hide());
        grp.addEventListener("focus", () => hover.stop(p, centreOf(grp)));
        grp.addEventListener("blur", () => hover.hide());
        grp.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hover.stop(p, centreOf(grp)); } });
        root.append(grp);
      }
      g.badges.forEach((b) => root.append(badgeNode(b.x, b.y, b.text, b.color)));
    },
    destroy() { root.remove(); },
  };
}

function leafletEngine(stage, hover, style) {
  const L = window.L;
  const map = L.map(stage, { zoomControl: true, attributionControl: true, keyboard: true, scrollWheelZoom: false,
    minZoom: TILE_LIMITS.minZoom, maxZoom: TILE_LIMITS.maxZoom });
  // Wheel zoom only after a click, so scrolling the page past a map never zooms it by accident.
  map.on("click focus", () => map.scrollWheelZoom.enable());
  map.on("mouseout blur", () => map.scrollWheelZoom.disable());
  // Real tiles end at maxNativeZoom; deeper zooms upscale them (soft but never blank). A missing tile shows the background.
  L.tileLayer(TILES, { minZoom: TILE_LIMITS.minZoom, maxZoom: TILE_LIMITS.maxZoom, maxNativeZoom: TILE_LIMITS.maxNativeZoom,
    errorTileUrl: BLANK_TILE, className: "base-tiles", attribution: ATTRIBUTION }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  const colors = slotColors();
  let fitted = false, last = null;

  function paint(scene) {
    layer.clearLayers();
    const ll = new Map(scene.points.map((p) => [p.id, L.latLng(p.lat, p.lon)]));
    const px = new Map([...ll].map(([id, v]) => [id, map.latLngToContainerPoint(v)]));
    const back = (p) => map.containerPointToLatLng([p.x, p.y]);
    const g = routeDrawing(scene.lines, (id) => px.get(id), style);
    for (const l of g.legs) L.polyline([back(l.a), back(l.b)], { color: cssVar("--surface"), weight: 8, opacity: 0.8, lineCap: "round", lineJoin: "round", interactive: false }).addTo(layer);
    const lines = g.legs.map((l) => L.polyline([back(l.a), back(l.b)], { color: l.color, weight: 4.5, opacity: 0.96, lineCap: "round", lineJoin: "round", dashArray: l.dash || null, interactive: false }).addTo(layer));
    // Wide invisible lines on top, so thin routes are easy to hover, tap or focus.
    const hitWeight = scene.lines.length > 1 ? 12 : 20;
    g.legs.forEach((l, i) => {
      const hit = L.polyline([back(l.a), back(l.b)], { color: "#000", weight: hitWeight, opacity: 0, lineCap: "round", className: "leg-hit", bubblingMouseEvents: false }).addTo(layer);
      const lit = (on) => lines[i].setStyle({ weight: on ? 7.5 : 4.5, opacity: on ? 1 : 0.96 });
      hit.on("mouseover click", (e) => { lit(true); hover.leg(l, e.originalEvent); });
      hit.on("mousemove", (e) => hover.move(e.originalEvent));
      hit.on("mouseout", () => { lit(false); hover.hide(); });
      const node = hit.getElement();
      if (node) {
        node.setAttribute("tabindex", "0"); node.setAttribute("role", "button"); node.setAttribute("aria-label", hover.legLabel(l));
        node.addEventListener("focus", () => { lit(true); hover.leg(l, centreOf(node)); });
        node.addEventListener("blur", () => { lit(false); hover.hide(); });
        node.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); hover.leg(l, centreOf(node)); } });
      }
    });
    const icon = (node, size, cls = "lf-icon") => L.divIcon({ html: node, className: cls, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
    for (const s of g.shapes) {
      L.marker(back(s), { interactive: false, keyboard: false,
        icon: icon(svg("svg", { width: 12, height: 12, viewBox: "0 0 12 12" }, marker(s.shape, 6, 6, s.color, 3.5)), 12) }).addTo(layer);
    }
    for (const a of g.arrows) {
      const glyph = svg("svg", { width: 14, height: 14, viewBox: "-7 -7 14 14" }, arrowPath(0, 0, a.angle, a.color));
      L.marker(back(a), { interactive: false, keyboard: false, icon: icon(glyph, 14) }).addTo(layer);
    }
    for (const b of g.badges) {
      const badge = h("span", { class: "lf-badge", style: `background:${b.color}` }, b.text);
      L.marker(back(b), { interactive: false, keyboard: false, icon: icon(badge, 16) }).addTo(layer);
    }
    const size = map.getSize();
    const plan = new Set(labelPlan(scene.points.map((p) => ({ id: p.id, name: p.name, ...px.get(p.id), visited: p.filled })), size.x, size.y));
    for (const p of scene.points) {
      const dot = h("span", { class: `lf-dot ${dotClass(p)}`, style: p.depot ? null : `--slot:${colors[p.slot]}` });
      const m = L.marker(ll.get(p.id), { icon: icon(dot, 20), keyboard: true, zIndexOffset: 500 }).addTo(layer);
      const mel = m.getElement();
      mel.setAttribute("aria-label", hover.stopLabel(p)); mel.setAttribute("role", "button");
      const side = labelSide({ name: p.name, x: px.get(p.id).x }, size.x);
      if (p.depot || plan.has(p.id)) m.bindTooltip(p.name, { permanent: true, direction: side, offset: [side === "right" ? 6 : -6, 0], className: "lf-label" });
      m.on("click mouseover", (e) => hover.stop(p, e.originalEvent));
      m.on("mousemove", (e) => hover.move(e.originalEvent));
      m.on("mouseout", () => hover.hide());
      mel.addEventListener("focus", () => hover.stop(p, centreOf(mel)));
      mel.addEventListener("blur", () => hover.hide());
    }
  }
  const repaint = () => { if (last) paint(last); };
  map.on("zoomend moveend resize", () => { hover.hide(); repaint(); });
  map.on("click", () => hover.hide());
  return {
    draw(scene) {
      last = scene;
      if (!fitted) { map.fitBounds(L.latLngBounds(scene.points.map((p) => [p.lat, p.lon])), { padding: [40, 40] }); fitted = true; }
      paint(scene);
    },
    invalidate() { map.invalidateSize(); },
    destroy() { map.off(); map.remove(); },
  };
}
