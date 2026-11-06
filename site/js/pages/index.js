// Page registry. To add a page (tickets 10, 11): create js/pages/<name>.js exporting a page object
//   { path: "map", title: "Map", render(el, ctx) }   // el = <main>; ctx.params = URLSearchParams
// and add it to this list. The nav and router are built from it; nothing else changes.
// Hash routes: #/<path>?key=value (e.g. #/instance?id=n10-seed3). `render` may be async and may
// return a cleanup function. Use js/lib/data.js to load results and js/lib/dom.js to build DOM.
import overview from "./overview.js";
import failures from "./failures.js";
import instance from "./instance.js";
import run from "./run.js";

export const pages = [overview, instance, run, failures];
export const defaultPath = "overview";
