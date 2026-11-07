// Headless-Chrome check of the map's Fullscreen button. Usage: node tests/site_fullscreen.mjs <baseUrl>
// For Leaflet and ?map=svg, desktop and phone, with the browser Fullscreen API and with it removed (the CSS fallback), on the
// Instance page: press Fullscreen with a real mouse click while the page's entrance animation is still running, and require
// that the map fills the viewport (figure == viewport, stage large and inside it), the page behind is inert, and Escape puts
// everything back and returns focus to the button. Prints JSON; exit 1 on any failure; 77 when Chrome is missing.
import { spawn } from "node:child_process";
import { mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.argv[2];
const CHROME = process.env.CHROME || ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"].find(existsSync);
if (!base || !CHROME) { console.error(base ? "no Chrome found" : "usage: site_fullscreen.mjs <baseUrl>"); process.exit(base ? 77 : 2); }

const chrome = spawn(CHROME, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${mkdtempSync(join(tmpdir(), "fs-"))}`, "--no-first-run", "--disable-gpu", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
const wsUrl = await new Promise((resolve, reject) => {
  let buf = "";
  chrome.stderr.on("data", (d) => { buf += d; const m = buf.match(/ws:\/\/\S+/); if (m) resolve(m[0]); });
  setTimeout(() => reject(new Error("chrome start timeout")), 15000);
});
const ws = new WebSocket(wsUrl);
let id = 0; const pending = new Map(); const handlers = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { const { ok, bad } = pending.get(m.id); pending.delete(m.id); m.error ? bad(new Error(m.error.message)) : ok(m.result); } else handlers.forEach((fn) => fn(m));
};
await new Promise((r) => (ws.onopen = r));
const send = (method, params = {}, sessionId) => new Promise((ok, bad) => { const i = ++id; pending.set(i, { ok, bad }); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const STATE = `(() => {
  const f = document.querySelector(".routemap"), st = f.querySelector(".map-stage"), b = f.querySelector(".map-full");
  const r = (e) => { const q = e.getBoundingClientRect(); return [q.left, q.top, q.width, q.height].map(Math.round); };
  return JSON.stringify({ vw: innerWidth, vh: innerHeight, fig: r(f), stage: r(st), full: f.classList.contains("is-full"), pressed: b.getAttribute("aria-pressed"),
    label: b.getAttribute("aria-label"), focusOnButton: document.activeElement === b, native: !!document.fullscreenElement,
    inertOutside: [...document.querySelectorAll("header, main > *")].filter((n) => !n.contains(f) && !f.contains(n)).every((n) => n.inert) && !!document.querySelector("header")?.inert,
    leafletH: (st.matches(".leaflet-container") ? st : st.querySelector(".leaflet-container"))?.getBoundingClientRect().height ?? null,
    leafletTiles: st.querySelectorAll(".leaflet-tile").length, leafletPane: st.querySelector(".leaflet-map-pane")?.childElementCount ?? 0 });
})()`;

const failures = []; const report = [];
for (const [name, query] of [["leaflet", ""], ["svg", "&map=svg"]]) {
  for (const [device, w, h, mobile] of [["desktop", 1280, 800, false], ["phone", 375, 812, true]]) {
    for (const api of [true, false]) {
      const { targetId } = await send("Target.createTarget", { url: "about:blank" });
      const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
      const s = (m, p) => send(m, p, sessionId);
      const errors = [];
      handlers.push((m) => { if (m.sessionId === sessionId && (m.method === "Runtime.exceptionThrown" || (m.method === "Runtime.consoleAPICalled" && m.params.type === "error"))) errors.push(JSON.stringify(m.params).slice(0, 200)); });
      await s("Runtime.enable"); await s("Page.enable");
      await s("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile });
      await s("Page.addScriptToEvaluateOnNewDocument", { source: `try { localStorage.setItem("theme", "dark"); } catch (e) {}` + (api ? "" : `Element.prototype.requestFullscreen = undefined;`) });
      await s("Page.navigate", { url: `${base}/#/instance?id=n10-seed1${query}` });
      const ev = async (expr) => (await s("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
      for (let i = 0; i < 60 && !(await ev(`!!document.querySelector(".map-full")`)); i++) await sleep(100);
      await ev(`document.querySelector(".map-full").scrollIntoView({ block: "center" })`);
      await sleep(150);
      const [cx, cy] = await ev(`(() => { const q = document.querySelector(".map-full").getBoundingClientRect(); return [q.left + q.width / 2, q.top + q.height / 2]; })()`);
      for (const type of ["mousePressed", "mouseReleased"]) await s("Input.dispatchMouseEvent", { type, x: cx, y: cy, button: "left", clickCount: 1 });
      await sleep(900);
      const on = JSON.parse(await ev(STATE));
      const tag = `${name}/${device}/${api ? "api" : "css"}`;
      const bad = [];
      if (!on.full) bad.push("not in fullscreen state");
      if (on.pressed !== "true") bad.push("aria-pressed not true");
      if (on.fig.join() !== [0, 0, on.vw, on.vh].join()) bad.push(`figure ${on.fig} is not the viewport ${on.vw}x${on.vh}`);
      if (on.stage[0] < 0 || on.stage[1] < 0 || on.stage[0] + on.stage[2] > on.vw || on.stage[1] + on.stage[3] > on.vh) bad.push(`stage ${on.stage} leaves the viewport`);
      if (on.stage[2] < on.vw - 24 || on.stage[3] < on.vh * 0.45) bad.push(`stage ${on.stage} is too small for ${on.vw}x${on.vh}`);
      if (name === "leaflet" && !(on.leafletH > on.vh * 0.45)) bad.push(`leaflet container height ${on.leafletH}`);
      if (!on.inertOutside) bad.push("page behind is not inert");
      await s("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
      await s("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
      await sleep(500);
      let off = JSON.parse(await ev(STATE));
      if (off.native) { await ev(`document.exitFullscreen()`); await sleep(400); off = JSON.parse(await ev(STATE)); } // headless may swallow Esc for native fullscreen
      if (off.full || off.pressed !== "false") bad.push("Escape did not leave fullscreen");
      if (!off.focusOnButton) bad.push("focus did not return to the Fullscreen button");
      if (off.stage[3] < 300 || off.fig[3] === on.fig[3]) bad.push(`layout not restored ${off.stage}`);
      if (await ev(`document.querySelector("header").inert || document.querySelector("main").inert`)) bad.push("page still inert after exit");
      if (errors.length) bad.push("console errors: " + errors.join(" | "));
      report.push({ tag, on: on.fig.concat(on.stage), native: on.native, problems: bad });
      bad.forEach((b) => failures.push(`${tag}: ${b}`));
      await send("Target.closeTarget", { targetId });
    }
  }
}
console.log(JSON.stringify(report, null, 1));
if (failures.length) console.error(failures.join("\n"));
chrome.kill();
process.exit(failures.length ? 1 : 0);
