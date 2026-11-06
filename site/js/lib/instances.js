// Instance files (locations, windows, distance matrix) served under /instances/. Cached like lib/data.js.
const cache = new Map();

export function loadInstance(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/instances/${encodeURIComponent(id)}.json`, { cache: "no-store" }).then((res) => {
      if (!res.ok) throw new Error(`Could not load instance ${id} (${res.status}). Start the server with --instances pointing at the instances folder.`);
      return res.json();
    }));
    cache.get(id).catch(() => cache.delete(id));
  }
  return cache.get(id);
}

/** Add the map stylesheet once. Pages call this so no shared file needs editing. */
export function ensureMapCss() {
  if (document.getElementById("map-css")) return;
  const link = document.createElement("link");
  link.id = "map-css";
  link.rel = "stylesheet";
  link.href = "css/map.css";
  document.head.append(link);
}

/** Keep the URL shareable without triggering the router (no re-render, focus stays put). */
export function replaceHashParams(path, params) {
  history.replaceState(null, "", `#/${path}?${params}`);
}
