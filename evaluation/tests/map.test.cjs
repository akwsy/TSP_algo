// Dependency-free Node check for the pure map geometry helpers (projection, bounds, zoom, scale bar, label placement).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/map.js'), 'utf8'), context);
const G = context.MapGeo;
let checks = 0;
const ok = (value, message) => { assert.ok(value, message); checks++; };
const near = (actual, expected, tolerance, message) => { assert.ok(Math.abs(actual - expected) <= tolerance, `${message}: ${actual} vs ${expected}`); checks++; };

// Projection: aspect ratio and orientation.
const eq = G.project(0, 1, 0, 0), north = G.project(1, 0, 0, 0);
near(eq.x, G.KM_PER_DEGREE, 1e-9, '1 degree of longitude at the equator');
near(north.y, -G.KM_PER_DEGREE, 1e-9, 'north is screen-up (negative y)');
near(G.project(0, 1, 60, 0).x, G.KM_PER_DEGREE / 2, 1e-6, 'longitude shrinks by cos(60 deg)');
near(G.project(3.1, 101.7, 3.1, 101.7).x, 0, 1e-12, 'origin maps to zero');
near(G.project(3, 101.1, 3, 101).x, 11.1195 * Math.cos(3 * Math.PI / 180), 1e-6, 'east offset at 3 N');
const c = G.centre([{ latitude: 1, longitude: 100 }, { latitude: 5, longitude: 104 }]);
near(c.lat0, 3, 0, 'centre latitude'); near(c.lon0, 102, 0, 'centre longitude');

// Bounds and fit.
const b = G.bounds([{ x: -10, y: 5 }, { x: 30, y: -15 }, { x: 0, y: 0 }]);
ok(b.minX === -10 && b.maxX === 30 && b.minY === -15 && b.maxY === 5, 'bounds');
const fit = G.fitView(b, 800, 400, 50);
near(fit.k, Math.min(700 / 40, 300 / 20), 1e-9, 'fit scale picks the tighter axis');
for (const p of [{ x: -10, y: 5 }, { x: 30, y: -15 }]) {
  const s = G.toScreen(fit, p);
  ok(s.x >= 50 - 1e-9 && s.x <= 750 + 1e-9 && s.y >= 50 - 1e-9 && s.y <= 350 + 1e-9, 'fitted points stay inside the padding');
}
near(G.toScreen(fit, { x: 10, y: -5 }).x, 400, 1e-9, 'bounds centre is the viewport centre');
const single = G.fitView(G.bounds([{ x: 3, y: 4 }]), 600, 400, 50);
ok(Number.isFinite(single.k) && single.k > 0, 'single point has a finite fit');
near(G.toScreen(single, { x: 3, y: 4 }).y, 200, 1e-9, 'single point is centred');
const s7 = G.toScreen(fit, { x: 7, y: -3 }), back = G.toWorld(fit, s7.x, s7.y);
near(back.x, 7, 1e-9, 'toWorld inverts toScreen'); near(back.y, -3, 1e-9, 'toWorld inverts toScreen (y)');

// Zoom keeps the anchor fixed and clamps.
const z = G.zoomAt(fit, fit, 2, 123, 77), before = G.toWorld(fit, 123, 77), after = G.toWorld(z, 123, 77);
near(after.x, before.x, 1e-9, 'zoom anchor x'); near(after.y, before.y, 1e-9, 'zoom anchor y');
near(z.k, fit.k * 2, 1e-9, 'zoom factor');
near(G.zoomAt(fit, fit, 1e9, 0, 0).k, fit.k * 400, 1e-6, 'max zoom clamp');
near(G.zoomAt(fit, fit, 1e-9, 0, 0).k, fit.k * .5, 1e-9, 'min zoom clamp');
const p2 = G.panBy(fit, 5, -7);
ok(p2.tx === fit.tx + 5 && p2.ty === fit.ty - 7 && p2.k === fit.k, 'pan');
const rp = G.revealPan(-30, 200, 800, 400, 24);
ok(rp.dx === 54 && rp.dy === 0, 'reveal pan brings an off-screen point inside');
ok(G.revealPan(400, 200, 800, 400).dx === 0, 'no pan when visible');

// Scale bar.
let sb = G.scaleBar(10, 140);
ok(sb.km === 10 && sb.label === '10 km' && sb.px === 100, `scale bar at 10 px/km: ${JSON.stringify(sb)}`);
sb = G.scaleBar(2, 140); ok(sb.km === 50 && sb.label === '50 km', 'scale bar at 2 px/km');
sb = G.scaleBar(1000, 140); ok(sb.km === .1 && sb.label === '100 m', `sub-km label: ${JSON.stringify(sb)}`);
for (const k of [.01, .3, 1, 7, 33, 250, 5000]) {
  const bar = G.scaleBar(k, 140);
  ok(bar.px <= 140 + 1e-9 && bar.px > 140 / 2.5 - 1e-9, `scale bar fits at ${k} px/km (${bar.px})`);
}
ok(G.scaleBar(0).km === 0, 'degenerate scale');
near(G.angleDegrees(0, 0, 1, 1), 45, 1e-9, 'arrow angle'); near(G.angleDegrees(0, 0, -1, 0), 180, 1e-9, 'arrow angle west');

// Label placement.
const item = (id, x, y, extra = {}) => ({ id, x, y, w: 60, h: 14, r: 8, priority: 100, ...extra });
let out = G.placeLabels([item(0, 100, 100)], 400, 300);
ok(out.get(0).anchor === 'start' && out.get(0).x === 12, 'lone label goes east');
out = G.placeLabels([item(0, 380, 100)], 400, 300);
ok(out.get(0).anchor === 'end', 'label flips west at the right edge');
const many = Array.from({ length: 60 }, (_, i) => item(i, (i * 37) % 380 + 10, (i * 53) % 280 + 10, { priority: 200 - i }));
out = G.placeLabels(many, 400, 300);
const boxes = [];
for (const [id, at] of out) {
  const m = many[id], x = m.x + at.x - (at.anchor === 'middle' ? 30 : at.anchor === 'end' ? 60 : 0), y = m.y + at.y - 7;
  boxes.push({ x, y, w: 60, h: 14 });
}
let overlapFree = true;
for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
  const a = boxes[i], o = boxes[j];
  if (a.x < o.x + o.w && o.x < a.x + a.w && a.y < o.y + o.h && o.y < a.y + a.h) overlapFree = false;
}
ok(overlapFree, 'no two placed labels overlap');
ok(out.size > 0 && out.size < 60, 'dense map hides some labels');
const pair = G.placeLabels([item(0, 200, 150, { priority: 1 }), item(1, 230, 150, { priority: 9 })], 400, 300);
ok(pair.has(1), 'higher priority label wins a contested spot');
const crowd = [item(0, 100, 100, { priority: 1000, force: true }), item(1, 100, 78), item(2, 100, 122), item(3, 170, 100), item(4, 30, 100)];
ok(G.placeLabels(crowd, 400, 300).has(0), 'forced label always placed');
ok(G.placeLabels([item(0, 5000, 5000)], 400, 300).size === 0, 'off-screen labels skipped');
ok(G.textWidth('abcd') < G.textWidth('abcdefgh'), 'text width grows');
console.log(`PASS: ${checks} map geometry checks (projection, fit, zoom, scale bar, label placement).`);
