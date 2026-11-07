import { h, selectKey, findSelect } from "./lib/dom.js";
import { pages, defaultPath } from "./pages/index.js";
import { resolveTheme, nextTheme, motionAllowed } from "./lib/motion.js";
import { motionOn } from "./lib/fx.js";

const main = document.getElementById("main");
const nav = document.getElementById("nav");
const themeBtn = document.getElementById("theme");
const motionBtn = document.getElementById("motion");
const root = document.documentElement;
let cleanup = null;

const read = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
const write = (key, value) => { try { localStorage.setItem(key, value); } catch { /* storage blocked */ } };

// ---- theme: dark by default; the button cycles dark, light, system (remembered when storage allows) ----
const NAMES = { dark: "Dark", light: "Light", system: "System" };
let theme = resolveTheme(read("theme"));
function applyTheme() {
  if (theme === "system") delete root.dataset.theme; else root.dataset.theme = theme;
  const next = nextTheme(theme);
  // Visible text "Theme Dark" is the start of the accessible name; the hidden part says what pressing does.
  themeBtn.replaceChildren(h("span", { class: "lamp theme-lamp", "aria-hidden": "true" }), h("span", { class: "txt-long" }, "Theme "), NAMES[theme],
    h("span", { class: "sr-only" }, `, press for ${NAMES[next].toLowerCase()}`));
}
themeBtn.addEventListener("click", () => {
  theme = nextTheme(theme);
  write("theme", theme);
  applyTheme();
  window.dispatchEvent(new Event("themechange"));
});
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (theme === "system") window.dispatchEvent(new Event("themechange")); });
applyTheme();

// ---- motion: off when the system asks for reduced motion or the visitor presses "Reduce motion" ----
const systemReduce = matchMedia("(prefers-reduced-motion: reduce)");
function applyMotion() {
  const allowed = motionAllowed(systemReduce.matches, read("motion"));
  root.dataset.motion = allowed ? "full" : "reduce";
  motionBtn.setAttribute("aria-pressed", String(!allowed));
  if (systemReduce.matches) {
    motionBtn.setAttribute("aria-disabled", "true");
    motionBtn.title = "Motion is reduced by your system setting";
  } else {
    motionBtn.removeAttribute("aria-disabled");
    motionBtn.title = allowed ? "Turn animations off" : "Turn animations back on";
  }
  window.dispatchEvent(new Event("motionchange"));
}
motionBtn.addEventListener("click", () => {
  if (systemReduce.matches) return; // the system setting always wins
  write("motion", root.dataset.motion === "reduce" ? "full" : "reduce");
  applyMotion();
});
systemReduce.addEventListener("change", applyMotion);
applyMotion();

// ---- router ----
function parseHash() {
  const [path, query = ""] = location.hash.replace(/^#\/?/, "").split("?");
  return { path: path || defaultPath, params: new URLSearchParams(query) };
}

const ink = h("span", { class: "nav-ink", "aria-hidden": "true" });
nav.append(...pages.map((p) => h("a", { href: `#/${p.path}`, "data-path": p.path }, p.title)), ink);
/** Slide the glowing bar under the current tab. */
function moveInk() {
  const a = nav.querySelector("[aria-current]");
  if (!a) { ink.style.width = "0"; return; }
  ink.style.width = `${a.offsetWidth - 20}px`;
  ink.style.transform = `translate(${a.offsetLeft + 10}px, ${a.offsetTop + a.offsetHeight - nav.clientHeight}px)`;
}
addEventListener("resize", moveInk);

let lastPath = null;
async function route() {
  const { path, params } = parseHash();
  const page = pages.find((p) => p.path === path);
  for (const a of nav.querySelectorAll("a")) {
    if (a.dataset.path === (page ? page.path : "")) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  moveInk();
  nav.querySelector("[aria-current]")?.scrollIntoView?.({ inline: "center", block: "nearest" });
  // A filter <select> changed the URL: after the re-render keep keyboard focus on that same select instead of dropping it to <main>.
  const keepFocus = document.activeElement instanceof HTMLSelectElement && main.contains(document.activeElement) ? selectKey(document.activeElement) : null;
  if (typeof cleanup === "function") cleanup();
  cleanup = null;
  main.classList.remove("entering");
  main.replaceChildren();
  if (!page) {
    document.title = "Not found - Routing results";
    main.append(h("h1", {}, "Page not found"), h("p", { class: "lede" }, "Choose a page from the menu."));
    return;
  }
  document.title = `${page.title} - Routing results`;
  try {
    cleanup = await page.render(main, { params, navigate: (to) => { location.hash = `#/${to}`; } });
  } catch (err) {
    console.warn(err);
    main.replaceChildren(h("h1", {}, page.title), h("div", { class: "error", role: "alert" }, err.message));
  }
  // A new view assembles panel by panel; a filter change on the same view only refreshes, without the entrance.
  if (motionOn() && path !== lastPath) {
    [...main.children].forEach((c, i) => c.style.setProperty("--i", String(Math.min(i, 8))));
    void main.offsetWidth;
    main.classList.add("entering");
  }
  lastPath = path;
  (findSelect(main, keepFocus) || main).focus({ preventScroll: true });
}
addEventListener("hashchange", route);
route();
