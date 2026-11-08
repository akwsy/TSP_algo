// Page registry. To add a page (tickets 10, 11): create js/pages/<name>.js exporting a page object
//   { path: "map", title: "Map", render(el, ctx) }   // el = <main>; ctx.params = URLSearchParams
// and add it to this list. The nav and router are built from it; nothing else changes.
// Hash routes: #/<path>?key=value (e.g. #/instance?id=n10-seed3). `render` may be async and may
// return a cleanup function. Use js/lib/data.js to load results and js/lib/dom.js to build DOM.
// View toggle (lib/view.js): a page that depends on it sets `fullView` on its page object:
//   "ready"   the page renders getView() === "full" itself (and is re-rendered when the choice changes);
//   "pending" the page still shows first-day content; the router adds a plain-words "coming to this page" note.
// Pages without `fullView` ignore the toggle. A ticket that adds the full-run view to a page switches "pending" to "ready".
import overview from "./overview.js";
import failures from "./failures.js";
import scaling from "./scaling.js";
import history from "./history.js";
import instance from "./instance.js";
import run from "./run.js";
import compare from "./compare.js";

export const pages = [overview, compare, scaling, instance, run, history, failures];
export const defaultPath = "overview";
