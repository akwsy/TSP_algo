// Interactive route map. Leaflet (pinned, from cdnjs) when it loads in time, otherwise a plain projected
// SVG drawing of the same scene, so the map never goes blank. Force the fallback with ?map=svg on the page URL.
import { h } from "./dom.js";
import { buildScene, chooseEngine, project, slotColors } from "./mapmodel.js";

const LEAFLET = "1.9.4";
const BASE = `https://cdnjs.cloudflare.com/ajax/libs/leaflet/${LEAFLET}/`;
const SVGNS = "http://www.w3.org/2000/svg";
// Subresource integrity for the pinned files (sha512 of the cdnjs files, matching the cdnjs API).
const SRI = {
  js: "sha512-puJW3E/qXDqYp9IfhAI54BJEaWIfloJ7JWs7OeD5i6ruC9JZL1gERT1wjtwXFlh7CjE7ZJ+/vcRZRkIYIb6p4g==",
  css: "sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw==",
};
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
export const algorithmColor = (index) => cssVar(`--c${(index % 6) + 1}`);

function svg(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  el.append(...kids.flat().filter(Boolean));
  return el;
}

/** Colour legend for the four slots plus the visited/skipped key. */
export function slotLegend() {
  const cols = slotColors();
  const names = ["06:00-10:30", "10:30-15:00", "15:00-19:30", "19:30-24:00"];
  return h("ul", { class: "legend", "aria-label": "Map key" },
    cols.map((c, i) => h("li", {}, h("span", { class: "dot filled", style: `background:${c}` }), `Slot ${i + 1} ${names[i]}`)),
    h("li", {}, h("span", { class: "dot filled", style: "background:var(--muted)" }), "Filled: visited"),
    h("li", {}, h("span", { class: "dot hollow" }), "Hollow: skipped"),
    h("li", {}, h("span", { class: "dot depot" }), "Square: depot"));
}

/**
 * createRouteMap(instance, { entries, forceSvg, height }) -> { el, setEntries(entries), destroy() }
 * entries = [{ id, label, color, dash, run }]; `color`/`dash` are chosen by the caller (per-algorithm styling).
 */
export function createRouteMap(instance, opts) {
  let entries = opts.entries;
  let engine = null; // { draw(scene), destroy() }
  const detail = h("div", { class: "map-detail", role: "status", "aria-live": "polite" }, "Hover or press a location for details.");
  const stage = h("div", { class: "map-stage", style: opts.height ? `height:${opts.height}px` : null });
  const note = h("p", { class: "meta map-note", hidden: true });
  const el = h("figure", { class: "routemap" }, stage, note, detail);
  let dead = false;

  function show(point, scene) {
    const lines = [`${point.name}${point.depot ? " (depot)" : ""}`, `Window: ${point.window}`, ...point.info];
    detail.replaceChildren(h("strong", {}, lines[0]), ...lines.slice(1).map((t) => h("div", {}, t)));
  }
  const scene = () => buildScene(instance, entries);
  const style = (id) => entries.find((e) => e.id === id) || {};

  const ready = chooseEngine(loadLeaflet, 4000, opts.forceSvg).then((name) => {
    if (dead) return;
    engine = name === "leaflet" ? leafletEngine(stage, instance, show, style) : svgEngine(stage, instance, show, style);
    el.dataset.engine = name;
    if (name === "svg") {
      note.hidden = false;
      note.textContent = opts.forceSvg ? "Plain map (forced)." : "Street map unavailable here, so this is a plain drawing of the same locations and routes.";
    }
    engine.draw(scene());
  });

  return {
    el,
    ready,
    setEntries(next) { entries = next; if (engine) engine.draw(scene()); },
    destroy() { dead = true; engine?.destroy(); },
  };
}

function dotClass(p) {
  return `${p.depot ? "depot" : p.filled ? "filled" : "hollow"}`;
}

function svgEngine(stage, instance, show, style) {
  const W = 640, H = 480;
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "map-svg", role: "group", "aria-label": "Route map (plain drawing)" });
  stage.replaceChildren(root);
  stage.style.height = "auto";
  stage.style.aspectRatio = `${W} / ${H}`;
  const colors = slotColors();
  return {
    draw(scene) {
      const xy = project(scene.points, W, H, 36);
      const pos = new Map(scene.points.map((p, i) => [p.id, xy[i]]));
      root.replaceChildren();
      for (const line of scene.lines) {
        const s = style(line.entry);
        root.append(svg("polyline", { class: "route", fill: "none", stroke: s.color, "stroke-width": 3.5, "stroke-dasharray": s.dash || null,
          "stroke-linejoin": "round", "stroke-linecap": "round", opacity: 0.9,
          points: line.ids.map((id) => `${pos.get(id).x.toFixed(1)},${pos.get(id).y.toFixed(1)}`).join(" ") }));
      }
      for (const p of scene.points) {
        const { x, y } = pos.get(p.id);
        const label = `${p.name}. Window ${p.window}. ${p.info.join(". ")}`;
        const mark = p.depot
          ? svg("rect", { x: x - 8, y: y - 8, width: 16, height: 16, class: "pt depot" })
          : svg("circle", { cx: x, cy: y, r: p.filled ? 7 : 6, class: `pt ${dotClass(p)}`, fill: p.filled ? colors[p.slot] : "var(--surface)",
            stroke: p.filled ? "var(--text)" : colors[p.slot], "stroke-width": p.filled ? 1.5 : 3 });
        const ring = !p.depot && !p.filled ? svg("circle", { cx: x, cy: y, r: 8.5, fill: "none", stroke: "var(--muted)", "stroke-width": 1.2 }) : null;
        const g = svg("g", { tabindex: 0, role: "button", "aria-label": label, class: "pt-group" }, ring, mark, svg("title", {}, label));
        const pick = () => show(p, scene);
        g.addEventListener("click", pick);
        g.addEventListener("focus", pick);
        g.addEventListener("mouseenter", pick);
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
        root.append(g);
      }
      for (const b of scene.badges) {
        const { x, y } = pos.get(b.id);
        const s = style(b.entry);
        const bx = x + 9 + b.k * 14, by = y - 9 - b.k * 4;
        root.append(svg("g", { class: "badge-g", "aria-hidden": "true" },
          svg("circle", { cx: bx, cy: by, r: 8, fill: s.color, stroke: "var(--surface)", "stroke-width": 1.5 }),
          svg("text", { x: bx, y: by + 3.5, "text-anchor": "middle", class: "badge-t" }, b.text)));
      }
    },
    destroy() { root.remove(); },
  };
}

function leafletEngine(stage, instance, show, style) {
  const L = window.L;
  const map = L.map(stage, { zoomControl: true, attributionControl: true, keyboard: true, scrollWheelZoom: false });
  // Wheel zoom only after a click, so scrolling the page past a map never zooms it by accident.
  map.on("click focus", () => map.scrollWheelZoom.enable());
  map.on("mouseout blur", () => map.scrollWheelZoom.disable());
  const onEsc = (e) => { if (e.key === "Escape") map.closePopup(); };
  document.addEventListener("keydown", onEsc, true);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  const layer = L.layerGroup().addTo(map);
  const colors = slotColors();
  let fitted = false;
  return {
    draw(scene) {
      layer.clearLayers();
      const at = new Map(scene.points.map((p) => [p.id, [p.lat, p.lon]]));
      for (const line of scene.lines) {
        const s = style(line.entry);
        L.polyline(line.ids.map((id) => at.get(id)), { color: s.color, weight: 4, opacity: 0.9, dashArray: s.dash || null }).addTo(layer);
      }
      for (const p of scene.points) {
        const icon = h("span", { class: `lf-dot ${dotClass(p)}`, style: p.depot ? null : `--slot:${colors[p.slot]}` });
        const marker = L.marker(at.get(p.id), { icon: L.divIcon({ html: icon, className: "lf-icon", iconSize: [20, 20] }),
          title: `${p.name}. ${p.info.join(". ")}`, keyboard: true }).addTo(layer);
        const tip = h("div", {}, h("strong", {}, p.name), h("div", {}, `Window: ${p.window}`), p.info.map((t) => h("div", {}, t)));
        marker.bindTooltip(tip.cloneNode(true), { direction: "top", offset: [0, -8] });
        marker.bindPopup(tip);
        marker.on("click focus", () => show(p, scene));
      }
      for (const b of scene.badges) {
        const s = style(b.entry);
        const badge = h("span", { class: "lf-badge", style: `background:${s.color}` }, b.text);
        L.marker(at.get(b.id), { interactive: false, keyboard: false,
          icon: L.divIcon({ html: badge, className: "lf-icon", iconSize: [18, 18], iconAnchor: [-4 - b.k * 14, 22 + b.k * 4] }) }).addTo(layer);
      }
      if (!fitted) { map.fitBounds(L.latLngBounds([...at.values()]), { padding: [30, 30] }); fitted = true; }
    },
    destroy() { document.removeEventListener("keydown", onEsc, true); map.remove(); },
  };
}
