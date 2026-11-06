// Headless-Chrome smoke test for the website. Usage:
//   node tests/site_smoke.mjs <baseUrl> [--shots <dir>] [--matrix] [--wait <ms>]
// Loads every page from a fresh tab and prints JSON: per page, console errors/warnings, uncaught exceptions,
// failed requests to the site's own origin, and the main heading. --matrix repeats for desktop/phone x light/dark
// (and writes PNGs with --shots). Exit code 1 if any page has an error. Needs Google Chrome (CHROME env overrides).
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const base = args[0];
const opt = (name, def) => (args.includes(name) ? args[args.indexOf(name) + 1] : def);
const shots = opt("--shots", null);
const waitMs = Number(opt("--wait", 6000));
const CHROME = process.env.CHROME || [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
].find(existsSync);
if (!base || !CHROME) { console.error(base ? "no Chrome found" : "usage: site_smoke.mjs <baseUrl>"); process.exit(base ? 77 : 2); }

const PAGES = ["overview", "scaling", "instance", "run", "history", "failures"].map((p) => (p === "instance" ? "instance?id=n10-seed1" : p));
const MODES = args.includes("--matrix")
  ? [["desktop", 1280, 800, "light"], ["desktop", 1280, 800, "dark"], ["phone", 375, 812, "light"], ["phone", 375, 812, "dark"]]
  : [["desktop", 1280, 800, "light"]];

const profile = mkdtempSync(join(tmpdir(), "smoke-"));
const chrome = spawn(CHROME, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--disable-gpu", "about:blank"], { stdio: ["ignore", "ignore", "pipe"] });
const wsUrl = await new Promise((resolve, reject) => {
  let buf = "";
  chrome.stderr.on("data", (d) => { buf += d; const m = buf.match(/ws:\/\/\S+/); if (m) resolve(m[0]); });
  chrome.on("exit", () => reject(new Error("chrome exited")));
  setTimeout(() => reject(new Error("chrome start timeout")), 15000);
});

function connect(url) {
  const ws = new WebSocket(url);
  let id = 0; const pending = new Map(); const handlers = [];
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { const { ok, bad } = pending.get(m.id); pending.delete(m.id); m.error ? bad(new Error(m.error.message)) : ok(m.result); }
    else handlers.forEach((fn) => fn(m));
  };
  const opened = new Promise((r) => (ws.onopen = r));
  return { opened, ws, on: (fn) => handlers.push(fn),
    send: (method, params = {}, sessionId) => new Promise((ok, bad) => { const i = ++id; pending.set(i, { ok, bad }); ws.send(JSON.stringify({ id: i, method, params, sessionId })); }) };
}

const browser = connect(wsUrl);
await browser.opened;
const results = [];
for (const [device, w, hgt, scheme] of MODES) {
  for (const page of PAGES) {
    const { targetId } = await browser.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await browser.send("Target.attachToTarget", { targetId, flatten: true });
    const s = (m, p) => browser.send(m, p, sessionId);
    const entry = { page, device, scheme, errors: [], warnings: [], failedRequests: [] };
    browser.on((m) => {
      if (m.sessionId !== sessionId) return;
      if (m.method === "Runtime.exceptionThrown") entry.errors.push("exception: " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
      if (m.method === "Runtime.consoleAPICalled") {
        const text = m.params.args.map((a) => a.value ?? a.description ?? "").join(" ");
        if (m.params.type === "error") entry.errors.push("console.error: " + text);
        if (m.params.type === "warning") entry.warnings.push(text);
      }
      if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
        const u = m.params.entry.url || "";
        (u && !u.startsWith(base) ? entry.warnings : entry.errors).push("log: " + m.params.entry.text + " " + u);
      }
      if (m.method === "Network.loadingFailed") entry.failedRequests.push(m.params.errorText);
    });
    await s("Runtime.enable"); await s("Log.enable"); await s("Network.enable"); await s("Page.enable");
    await s("Emulation.setDeviceMetricsOverride", { width: w, height: hgt, deviceScaleFactor: 1, mobile: device === "phone" });
    await s("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: scheme }] });
    await s("Page.navigate", { url: `${base}/#/${page}` });
    await new Promise((r) => setTimeout(r, waitMs));
    const { result } = await s("Runtime.evaluate", { expression: "JSON.stringify({h1: document.querySelector('main h1')?.textContent, nan: /NaN|undefined|\\bfalse\\b|\\bnull\\b|\\[object/.test(document.body.innerText), hscroll: document.documentElement.scrollWidth > innerWidth || [...document.querySelectorAll('main *, header *')].some((e) => !e.closest('.table-wrap, #nav, pre, .leaflet-container, svg') && e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)})", returnByValue: true });
    Object.assign(entry, JSON.parse(result.value));
    if (!entry.h1) entry.errors.push("page rendered no heading");
    if (entry.nan) entry.errors.push("page text contains NaN/undefined");
    if (entry.hscroll) entry.errors.push("horizontal page scroll");
    if (shots) {
      mkdirSync(shots, { recursive: true });
      const { data } = await s("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
      writeFileSync(join(shots, `${page.split("?")[0]}-${device}-${scheme}.png`), Buffer.from(data, "base64"));
    }
    // fresh listener set per page: replace handlers by clearing is unnecessary since filtered by sessionId
    await browser.send("Target.closeTarget", { targetId });
    results.push(entry);
  }
}
console.log(JSON.stringify(results, null, 1));
chrome.kill();
process.exit(results.some((r) => r.errors.length) ? 1 : 0);
