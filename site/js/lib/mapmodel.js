// Pure logic for the map, instance explorer and route detail (no DOM). Tested by tests/test_site_mapmodel.py.

/** Minutes since midnight -> "HH:MM" (1440 -> "24:00"). null for missing values. */
export function clock(min) {
  if (typeof min !== "number" || !isFinite(min)) return null;
  const t = Math.round(min);
  return `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

export const windowText = (loc) => loc.isDepot ? "open all day" : `${clock(loc.opensAt)}-${clock(loc.closesAt)}`;

// Slot fills are an ordered light-to-dark ramp (early to late in the day); every dot also gets a
// strong outline, and visited versus skipped never relies on colour alone (filled vs hollow).
const SLOT_COLORS = ["#fde725", "#35b779", "#31688e", "#440154"];
export const slotColors = () => [...SLOT_COLORS];

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
