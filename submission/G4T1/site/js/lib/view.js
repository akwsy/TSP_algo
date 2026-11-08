// The "which view" choice shared by every page: "First day only" or "Until every place is visited".
//
// API (other pages import this module, like lib/data.js):
//   getView()                  -> "first" | "full"   (remembered in browser storage, default "first")
//   setView(id)                -> stores it and fires the event below when it changed
//   onViewChange(fn)           -> fn(viewId) on every change; returns an unsubscribe function
//   viewLabel(id)              -> the plain-word name shown to people
//   viewCountText(id, agg)     -> "30 examples per size" / "10 examples per size" / "not run yet"
//   comingSoonNote(pageName)   -> plain note for pages that do not have the full-run view yet
// Event: window dispatches a CustomEvent "viewchange" with detail { view } when the choice changes.
// The header toggle (js/app.js) calls setView; a page that shows view-dependent content re-renders on it
// (or the router can re-run the page). Pure helpers below are tested by tests/test_site_view.py.

export const VIEWS = ["first", "full"];
const LABELS = { first: "First day only", full: "Until every place is visited" };
const KEY = "view";

export const resolveView = (stored) => (VIEWS.includes(stored) ? stored : "first");
export const viewLabel = (id) => LABELS[resolveView(id)];

export const examplesPerSizeText = (n) =>
  typeof n === "number" ? `${n} example${n === 1 ? "" : "s"} per size` : "examples per size";

/** How many examples each size has in a view, in plain words. */
export function viewCountText(id, agg) {
  if (resolveView(id) === "first") return examplesPerSizeText(agg?.parameters?.instancesPerSize);
  const per = agg?.full?.instancesPerSize;
  const counts = per ? Object.values(per) : [];
  return counts.length ? examplesPerSizeText(Math.max(...counts)) : "not run yet";
}

/** Which view a key press on the toggle selects (arrows move, Home/End jump), or null for other keys. */
export function viewAfterKey(current, key) {
  const i = VIEWS.indexOf(resolveView(current));
  if (key === "ArrowRight" || key === "ArrowDown") return VIEWS[(i + 1) % VIEWS.length];
  if (key === "ArrowLeft" || key === "ArrowUp") return VIEWS[(i + VIEWS.length - 1) % VIEWS.length];
  if (key === "Home") return VIEWS[0];
  if (key === "End") return VIEWS[VIEWS.length - 1];
  return null;
}

export const comingSoonNote = (pageName) =>
  `The "Until every place is visited" view is coming to the ${pageName} page. For now this page shows the first day only.`;

// ---- state (browser only) ----
let current = null;
const read = () => { try { return localStorage.getItem(KEY); } catch { return null; } };
const write = (v) => { try { localStorage.setItem(KEY, v); } catch { /* storage blocked */ } };

export function getView() {
  if (current === null) current = resolveView(read());
  return current;
}

export function setView(id) {
  const next = resolveView(id);
  write(next);
  if (next === getView()) return;
  current = next;
  window.dispatchEvent(new CustomEvent("viewchange", { detail: { view: next } }));
}

export function onViewChange(fn) {
  const handler = (e) => fn(e.detail.view);
  window.addEventListener("viewchange", handler);
  return () => window.removeEventListener("viewchange", handler);
}
