// Pure logic for the map, instance explorer and route detail (no DOM). Tested by tests/test_site_mapmodel.py.

/** Minutes since midnight -> "HH:MM" (1440 -> "24:00"). null for missing values. */
export function clock(min) {
  if (typeof min !== "number" || !isFinite(min)) return null;
  const t = Math.round(min);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

export const windowText = (loc) => loc.isDepot ? "open all day" : `${clock(loc.opensAt)}-${clock(loc.closesAt)}`;

// Slot colours (early to late in the day) are theme tokens --slot-1..4 in charts.css, each at least 3:1 against the page in both
// themes. Visited versus skipped never relies on colour alone (filled vs hollow), and the slot also has a number (1 to 4).
export const slotColors = () => [1, 2, 3, 4].map((n) => `var(--slot-${n})`);

/** Stable colour slot per algorithm: index in sorted id order (site palette is --s1..--s6). */
export function algorithmColorIndex(ids) {
  return Object.fromEntries([...ids].sort().map((id, i) => [id, i]));
}

const validRoute = (run) => run && run.valid !== false && Array.isArray(run.route) && run.route.length > 1;

/** Every location with its role for one run: depot, visited (with order/arrival/wait) or skipped. */
export function mapPoints(instance, run) {
  const sched = new Map(((validRoute(run) && run.schedule) || []).map((s) => [s.id, s]));
  const order = new Map();
  if (validRoute(run)) run.route.filter((id, i) => i > 0 && i < run.route.length - 1).forEach((id, i) => order.set(id, i + 1));
  return instance.locations.map((l) => {
    const base = { id: l.id, name: l.name, lat: l.lat, lon: l.lon, slot: l.slot ?? null,
      window: l.isDepot ? null : [l.opensAt, l.closesAt] };
    if (l.isDepot) return { ...base, kind: "depot", order: null, arrive: null, wait: null };
    const s = sched.get(l.id);
    if (!order.has(l.id)) return { ...base, kind: "skipped", order: null, arrive: null, wait: null };
    return { ...base, kind: "visited", order: order.get(l.id), arrive: s?.arriveMinute ?? null,
      wait: s ? s.startMinute - s.arriveMinute : null };
  });
}

/** Step-by-step rows for one run: depart, each stop, return. */
export function routeSteps(instance, run) {
  if (!validRoute(run)) return [];
  const byId = new Map(instance.locations.map((l) => [l.id, l]));
  const sched = new Map((run.schedule || []).map((s) => [s.id, s]));
  const route = run.route;
  let cum = 0;
  return route.map((id, i) => {
    const l = byId.get(id) || { id, name: `#${id}` };
    const leg = i === 0 ? 0 : instance.distanceKm[route[i - 1]][id];
    cum += leg;
    const row = { id, name: l.name, slot: l.slot ?? null, window: l.isDepot ? null : [l.opensAt, l.closesAt],
      legKm: leg, cumKm: cum, arrive: null, wait: null, start: null, leave: null, step: i };
    if (i === 0) return { ...row, role: "depart", leave: instance.departureMinute };
    if (i === route.length - 1) return { ...row, role: "return", arrive: run.returnMinute };
    const s = sched.get(id);
    return { ...row, role: "stop", arrive: s?.arriveMinute ?? null, start: s?.startMinute ?? null,
      wait: s ? s.startMinute - s.arriveMinute : null, leave: s?.leaveMinute ?? null };
  });
}

/** Equirectangular projection of {lat,lon} points into a w x h box with padding; uniform scale, north up. */
export function project(points, w, h, pad = 20) {
  if (!points.length) return [];
  const lats = points.map((p) => p.lat), lons = points.map((p) => p.lon);
  const [minLat, maxLat, minLon, maxLon] = [Math.min(...lats), Math.max(...lats), Math.min(...lons), Math.max(...lons)];
  const k = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180);
  const spanX = (maxLon - minLon) * k, spanY = maxLat - minLat;
  const scale = Math.min(spanX ? (w - 2 * pad) / spanX : Infinity, spanY ? (h - 2 * pad) / spanY : Infinity);
  const s = isFinite(scale) ? scale : 0;
  const ox = (w - spanX * s) / 2, oy = (h - spanY * s) / 2;
  return points.map((p) => ({ x: ox + (p.lon - minLon) * k * s, y: oy + (maxLat - p.lat) * s }));
}

/** "leaflet" when the loader resolves in time (and fallback is not forced), otherwise "svg". Never throws. */
export async function chooseEngine(loadLeaflet, timeoutMs = 4000, forceSvg = false) {
  if (forceSvg) return "svg";
  let timer;
  try {
    await Promise.race([loadLeaflet(), new Promise((_, rej) => { timer = setTimeout(() => rej(new Error("timeout")), timeoutMs); })]);
    return "leaflet";
  } catch {
    return "svg";
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Everything a map engine needs to draw. `entries` = [{ id, label, run }] for the algorithms currently shown.
 * A location is `filled` (visited) if any shown route visits it; its `info` says what each shown run did.
 */
export function buildScene(instance, entries) {
  const per = entries.map((e) => ({ e, pts: new Map(mapPoints(instance, e.run).map((p) => [p.id, p])) }));
  const points = instance.locations.map((l) => {
    const info = per.map(({ e, pts }) => {
      const p = pts.get(l.id);
      if (p.kind === "depot") return null;
      if (p.kind === "skipped") return `${e.label}: skipped`;
      const wait = p.wait ? `, waits ${Math.round(p.wait)} min` : ", no wait";
      return `${e.label}: stop ${p.order}, arrives ${clock(p.arrive)}${wait}`;
    }).filter(Boolean);
    const depot = !!l.isDepot;
    return { id: l.id, name: l.name, lat: l.lat, lon: l.lon, depot, slot: l.slot ?? null,
      window: windowText(l), filled: !depot && per.some(({ pts }) => pts.get(l.id).kind === "visited"), info };
  });
  const lines = per.filter(({ e }) => validRoute(e.run)).map(({ e }) => ({ entry: e.id, ids: e.run.route }));
  const badges = per.flatMap(({ e, pts }, k) => [...pts.values()].filter((p) => p.kind === "visited")
    .map((p) => ({ entry: e.id, k, id: p.id, text: String(p.order) })));
  return { points, lines, badges };
}

// ---- Comparing algorithms on one map (all pure) ----

/** Perpendicular pixel offsets for n routes drawn side by side, centred on the true line. */
export function laneOffsets(n, gap = 4) {
  return Array.from({ length: n }, (_, k) => (k - (n - 1) / 2) * gap + 0);
}

/** Both ends of the segment a->b moved `off` pixels to the left of the direction of travel (screen space, y down). */
export function offsetSegment(a, b, off) {
  const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy);
  if (!len || !off) return [{ x: a.x, y: a.y }, { x: b.x, y: b.y }];
  const nx = dy / len * off, ny = -dx / len * off;
  return [{ x: a.x + nx, y: a.y + ny }, { x: b.x + nx, y: b.y + ny }];
}

const ok = (e) => validRoute(e.run) && typeof e.run.visited === "number";

/** Id of the best shown algorithm by the scoring rule (most places visited, then shortest distance); null if none valid. */
export function bestEntryId(entries) {
  const good = entries.filter(ok);
  if (!good.length) return null;
  return good.reduce((b, e) => (e.run.visited > b.run.visited || (e.run.visited === b.run.visited && e.run.distanceKm < b.run.distanceKm) ? e : b)).id;
}

const num = (v) => String(Math.round(v * 10) / 10);
function duration(min) {
  const t = Math.round(min);
  return t >= 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${t} min`;
}

/** One plain-words row per shown algorithm for the summary panel. */
export function summaryRows(entries) {
  const best = bestEntryId(entries);
  return entries.map((e) => {
    const r = e.run || {};
    const valid = ok(e);
    return { id: e.id, label: e.label ?? e.id, valid, best: valid && e.id === best,
      visited: valid ? r.visited : null,
      distance: valid ? `${num(r.distanceKm)} km` : null,
      time: valid ? duration(r.totalMinutes) : null };
  });
}

/** Plain-words notes of places visited by exactly one shown algorithm ("Only B visited: Town X"). Needs 2+ valid runs. */
export function differenceNotes(instance, entries) {
  const good = entries.filter((e) => validRoute(e.run));
  if (good.length < 2) return [];
  const sets = good.map((e) => new Set(mapPoints(instance, e.run).filter((p) => p.kind === "visited").map((p) => p.id)));
  const notes = [];
  good.forEach((e, k) => {
    const names = instance.locations.filter((l) => sets[k].has(l.id) && sets.every((s, j) => j === k || !s.has(l.id))).map((l) => l.name);
    if (names.length) notes.push(`Only ${e.label ?? e.id} visited: ${names.join(", ")}`);
  });
  return notes;
}

const LABEL_H = 14;
const labelWidth = (name) => Math.ceil(name.length * 6.4) + 8;

/** Which side of its marker a label goes on so it stays inside the box. */
export function labelSide(p, w) {
  return p.x + 10 + labelWidth(p.name) > w ? "left" : "right";
}

/** ids of the destinations whose name is shown permanently: visited first, then input order, never overlapping. */
export function labelPlan(points, w, h) {
  const boxes = [], keep = [];
  const order = [...points.keys()].sort((i, j) => (points[j].visited - points[i].visited) || i - j);
  for (const i of order) {
    const p = points[i], lw = labelWidth(p.name);
    const x0 = labelSide(p, w) === "right" ? p.x + 10 : p.x - 10 - lw;
    const box = [x0, p.y - LABEL_H / 2, x0 + lw, p.y + LABEL_H / 2];
    if (box[0] < 0 || box[2] > w || box[1] < 0 || box[3] > h) continue;
    if (boxes.some((b) => box[0] < b[2] && b[0] < box[2] && box[1] < b[3] && b[1] < box[3])) continue;
    boxes.push(box); keep.push(p.id);
  }
  return keep;
}

/** Names appear one zoom level past the initial fit, but never beyond what the map can reach. */
export function labelsVisible(zoom, fitZoom, maxZoom) {
  return zoom >= Math.min(fitZoom + 1, maxZoom);
}

/** Opacity of destinations that no shown route visits. */
export const FADED_OPACITY = 0.55;

/** WCAG contrast of `fg` drawn at `opacity` over `bg` (both #rrggbb). */
export function contrastRatio(fg, bg, opacity = 1) {
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const f = rgb(fg), b = rgb(bg);
  const eff = f.map((v, i) => Math.round(v * opacity + b[i] * (1 - opacity)));
  const [hi, lo] = [lum(eff), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Esri World Terrain Base: the service advertises levels 0-13, but from level 10 up it returns a grey "Map data not yet available"
 * placeholder (checked against the live service), so level 9 is the last real tile. Beyond it Leaflet upscales level 9 tiles up to 4x (level 11); 16x (level 13) looked too pixelated.
 */
export const TILE_LIMITS = Object.freeze({ minZoom: 1, maxNativeZoom: 9, maxZoom: 11 });

/** Zoom level forced into [min, max]; anything that is not a number falls back to min. */
export function clampZoom(z, min, max) {
  return Number.isFinite(z) ? Math.min(max, Math.max(min, z)) : min;
}

// ---- Hover details: when you get to a stop, how long you wait, when you leave; and the same for each leg ----
// Everything shown is derived from the rounded clock times, so "arrive + wait = leave" and "depart + travel = arrive"
// always agree on screen (no off-by-one-minute surprises).

export const formatClock = clock;

/** Minutes -> "45 min", "1 h", "1 h 12 min" (rounded to the nearest minute). */
export function formatDuration(min) {
  const t = Math.max(0, Math.round(min));
  if (t < 60) return `${t} min`;
  return t % 60 ? `${Math.floor(t / 60)} h ${t % 60} min` : `${Math.floor(t / 60)} h`;
}

const gap = (from, to) => formatDuration(Math.round(to) - Math.round(from));

/** What happens at one stop of one run. visited=false when the run skips it; the depot has leave (departure) and back (return). */
export function stopTimes(run, instance, id) {
  const l = instance.locations.find((x) => x.id === id);
  if (l?.isDepot) {
    if (!validRoute(run)) return { visited: false, depot: true };
    return { visited: true, depot: true, leave: clock(instance.departureMinute), back: clock(run.returnMinute) };
  }
  const s = validRoute(run) && run.route.slice(1, -1).includes(id) ? (run.schedule || []).find((x) => x.id === id) : null;
  if (!s) return { visited: false };
  const wait = Math.round(s.leaveMinute) - Math.round(s.arriveMinute);
  return { visited: true, arrive: clock(s.arriveMinute), leave: clock(s.leaveMinute),
    wait: wait > 0 ? `Waited ${formatDuration(wait)}` : "No wait" };
}

/** One plain line for a stop (from stopTimes), e.g. "Arrive 09:30 · Waited 1 h · Leave 10:30". */
export function stopLine(t) {
  if (!t.visited) return "not visited";
  return t.depot ? `Leave ${t.leave} · Back ${t.back}` : `Arrive ${t.arrive} · ${t.wait} · Leave ${t.leave}`;
}

/** Label/value rows for a leg (from legDetails). */
export function legRows(g) {
  return [["Travel time", g.travel], ["Departure", g.depart], ["Arrival", g.then ? `${g.arrive} (${g.then})` : g.arrive],
    ["Opening hours", g.opens], ["Distance", g.distance]];
}

/** The trip between two consecutive stops of a run (null if the run does not go straight from one to the other). */
export function legDetails(run, instance, fromId, toId) {
  if (!validRoute(run)) return null;
  const r = run.route;
  const i = r.findIndex((id, k) => id === fromId && r[k + 1] === toId);
  if (i < 0) return null;
  const byId = new Map(instance.locations.map((l) => [l.id, l]));
  const sched = new Map((run.schedule || []).map((s) => [s.id, s]));
  const depart = i === 0 ? instance.departureMinute : sched.get(fromId)?.leaveMinute;
  const last = i + 1 === r.length - 1;
  const arrive = last ? run.returnMinute : sched.get(toId)?.arriveMinute;
  if (typeof depart !== "number" || typeof arrive !== "number") return null;
  const to = byId.get(toId) || { id: toId, name: `#${toId}` };
  const wait = last ? 0 : Math.round(sched.get(toId).leaveMinute) - Math.round(arrive);
  return { from: byId.get(fromId)?.name ?? `#${fromId}`, to: to.name, depart: clock(depart), arrive: clock(arrive),
    travel: gap(depart, arrive), distance: `${num(instance.distanceKm[fromId][toId])} km`,
    opens: to.isDepot ? "open all day" : windowText(to), then: wait > 0 ? `then waits ${formatDuration(wait)}` : null };
}
