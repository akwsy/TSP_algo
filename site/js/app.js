import { h } from "./lib/dom.js";
import { pages, defaultPath } from "./pages/index.js";

const main = document.getElementById("main");
const nav = document.getElementById("nav");
const themeBtn = document.getElementById("theme");
let cleanup = null;

// ---- theme: follows the system unless the user picks one (remembered when storage allows) ----
const root = document.documentElement;
const systemDark = matchMedia("(prefers-color-scheme: dark)");
function currentTheme() {
  return root.dataset.theme || (systemDark.matches ? "dark" : "light");
}
function paintThemeButton() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  themeBtn.textContent = next === "dark" ? "Dark mode" : "Light mode";
  themeBtn.setAttribute("aria-label", `Switch to ${next} mode`);
}
try { const saved = localStorage.getItem("theme"); if (saved) root.dataset.theme = saved; } catch { /* storage blocked */ }
themeBtn.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch { /* storage blocked */ }
  paintThemeButton();
  window.dispatchEvent(new Event("themechange"));
});
systemDark.addEventListener("change", paintThemeButton);
paintThemeButton();

// ---- router ----
function parseHash() {
  const [path, query = ""] = location.hash.replace(/^#\/?/, "").split("?");
  return { path: path || defaultPath, params: new URLSearchParams(query) };
}

nav.append(...pages.map((p) => h("a", { href: `#/${p.path}`, "data-path": p.path }, p.title)));

async function route() {
  const { path, params } = parseHash();
  const page = pages.find((p) => p.path === path);
  for (const a of nav.children) {
    if (a.dataset.path === (page ? page.path : "")) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (typeof cleanup === "function") cleanup();
  cleanup = null;
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
  main.focus({ preventScroll: true });
}
addEventListener("hashchange", route);
route();
