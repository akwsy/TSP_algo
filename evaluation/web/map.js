'use strict';
// Offline map: pure geometry helpers (MapGeo, unit-tested in Node) and an SVG renderer with zoom/pan (MapView).
(function (root) {
  const KM_PER_DEGREE = 111.195;

  // ---------- Pure geometry ----------
  // Equirectangular projection around (lat0, lon0): x km east, y km SOUTH (screen-down), so longitude is scaled by cos(latitude).
  function project(lat, lon, lat0, lon0) {
    const cos = Math.max(.001, Math.cos(lat0 * Math.PI / 180));
    return { x: (lon - lon0) * cos * KM_PER_DEGREE, y: -(lat - lat0) * KM_PER_DEGREE };
  }
  function centre(items) {
    let minLat = Infinity, maxLat = -Infinity, minLon = Infinity, maxLon = -Infinity;
    for (const d of items) {
      minLat = Math.min(minLat, d.latitude); maxLat = Math.max(maxLat, d.latitude);
      minLon = Math.min(minLon, d.longitude); maxLon = Math.max(maxLon, d.longitude);
    }
    return { lat0: (minLat + maxLat) / 2, lon0: (minLon + maxLon) / 2 };
  }
  function bounds(points) {
    const b = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity };
    for (const p of points) {
      b.minX = Math.min(b.minX, p.x); b.maxX = Math.max(b.maxX, p.x);
      b.minY = Math.min(b.minY, p.y); b.maxY = Math.max(b.maxY, p.y);
    }
    return b;
  }
  // View = { k: pixels per km, tx, ty } with screen = k * world + t. Fit centres the bounds inside the padded viewport.
  function fitView(b, width, height, padding = 48, minSpanKm = 0.5) {
    const spanX = Math.max(b.maxX - b.minX, minSpanKm), spanY = Math.max(b.maxY - b.minY, minSpanKm);
    const availX = Math.max(10, width - 2 * padding), availY = Math.max(10, height - 2 * padding);
    const k = Math.min(availX / spanX, availY / spanY);
    const cx = (b.minX + b.maxX) / 2, cy = (b.minY + b.maxY) / 2;
    return { k, tx: width / 2 - cx * k, ty: height / 2 - cy * k };
  }
  function toScreen(view, p) { return { x: p.x * view.k + view.tx, y: p.y * view.k + view.ty }; }
  function toWorld(view, x, y) { return { x: (x - view.tx) / view.k, y: (y - view.ty) / view.k }; }
  // Zoom by `factor` keeping the world point under (cx, cy) fixed; scale is clamped to [fit.k * minZoom, fit.k * maxZoom].
  function zoomAt(view, fit, factor, cx, cy, minZoom = .5, maxZoom = 400) {
    const k = Math.min(fit.k * maxZoom, Math.max(fit.k * minZoom, view.k * factor));
    const w = toWorld(view, cx, cy);
    return { k, tx: cx - w.x * k, ty: cy - w.y * k };
  }
  function panBy(view, dx, dy) { return { k: view.k, tx: view.tx + dx, ty: view.ty + dy }; }
  // Smallest pan that brings a screen point at least `margin` px inside the viewport.
  function revealPan(x, y, width, height, margin = 24) {
    const clamp = (v, lo, hi) => v < lo ? lo - v : v > hi ? hi - v : 0;
    return { dx: clamp(x, margin, width - margin), dy: clamp(y, margin, height - margin) };
  }
  // Scale bar: a "nice" 1/2/5 x 10^n km length that fits in maxPx pixels.
  function scaleBar(pxPerKm, maxPx = 140) {
    if (!(pxPerKm > 0)) return { km: 0, px: 0, label: '' };
    const raw = maxPx / pxPerKm, pow = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / pow;
    const km = (m >= 5 ? 5 : m >= 2 ? 2 : 1) * pow;
    const label = km >= 1 ? `${+km.toPrecision(6)} km` : `${Math.round(km * 1000)} m`;
    return { km, px: km * pxPerKm, label };
  }
  function angleDegrees(x1, y1, x2, y2) { return Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI; }
  const overlaps = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
  // Greedy label placement. items: [{ id, x, y, w, h, r, priority, force }] in screen px (x,y = marker centre, r = marker radius).
  // All markers are obstacles. Each label tries E, W, N, S of its marker and is skipped if none is free,
  // unless `force` (selected/depot), which takes its first candidate. Returns Map id -> { x, y, anchor } (x,y = text origin offset from the marker).
  function placeLabels(items, width, height) {
    const placed = [], result = new Map();
    const obstacles = items.map(i => ({ x: i.x - i.r, y: i.y - i.r, w: 2 * i.r, h: 2 * i.r }));
    const order = [...items].sort((a, b) => (b.priority - a.priority) || (a.id - b.id));
    const inView = box => box.x >= 0 && box.y >= 0 && box.x + box.w <= width && box.y + box.h <= height;
    for (const item of order) {
      if (item.x < -20 || item.y < -20 || item.x > width + 20 || item.y > height + 20) continue;
      const { x, y, w, h, r } = item, gap = 4;
      const candidates = [
        { box: { x: x + r + gap, y: y - h / 2, w, h }, anchor: 'start', ox: r + gap, oy: 0 },
        { box: { x: x - r - gap - w, y: y - h / 2, w, h }, anchor: 'end', ox: -r - gap, oy: 0 },
        { box: { x: x - w / 2, y: y - r - gap - h, w, h }, anchor: 'middle', ox: 0, oy: -r - gap - h / 2 },
        { box: { x: x - w / 2, y: y + r + gap, w, h }, anchor: 'middle', ox: 0, oy: r + gap + h / 2 }
      ];
      let choice = candidates.find(c => inView(c.box) && !placed.some(p => overlaps(p, c.box))
        && !obstacles.some((o, n) => items[n] !== item && overlaps(o, c.box)));
      if (!choice && item.force) choice = candidates[0];
      if (!choice) continue;
      placed.push(choice.box);
      result.set(item.id, { x: choice.ox, y: choice.oy, anchor: choice.anchor });
    }
    return result;
  }
  const textWidth = (text, fontPx = 12) => Math.ceil(String(text).length * fontPx * .56) + 4;
  root.MapGeo = { KM_PER_DEGREE, project, centre, bounds, fitView, toScreen, toWorld, zoomAt, panBy, revealPan, scaleBar, angleDegrees, placeLabels, textWidth };

  // ---------- Rendering (browser only) ----------
  if (typeof document === 'undefined') return;
  const G = root.MapGeo;
  const esc = v => String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const MAX_LABEL_CHARS = 24, ARROW_MIN_PX = 30, CLICK_SLOP = 4;
  const V = { svg: null, fitKey: null, fit: null, view: null, touched: false, size: '', ctx: null, points: [], markers: [], arrows: [], labelsOf: new Map(), raf: 0, dragged: false, controls: false };

  function shortName(name) { return name.length > MAX_LABEL_CHARS ? `${name.slice(0, MAX_LABEL_CHARS - 1)}…` : name; }
  
  function draw(ctx) {
    const svg = ctx.svg, width = Math.round(svg.clientWidth);
    V.svg = svg; V.ctx = ctx;
    if (!width) return [];
    const height = Math.max(320, Math.min(520, Math.round(width * .62)));
    const ds = ctx.destinations, c = G.centre(ds);
    const points = ds.map(d => G.project(d.latitude, d.longitude, c.lat0, c.lon0));
    V.points = points;
    const fit = G.fitView(G.bounds(points), width, height);
    const size = `${width}x${height}`;
    if (V.fitKey !== ctx.fitKey || !V.view) { V.view = { ...fit }; V.touched = false; }
    else if (!V.touched) V.view = { ...fit };
    V.fitKey = ctx.fitKey; V.fit = fit; V.size = size;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('tabindex', '0');
    svg.setAttribute('aria-describedby', 'map-keys');
    svg.innerHTML = build(ctx, points);
    V.markers = [...svg.querySelectorAll('#map-screen > [data-wx]')];
    V.arrows = [...svg.querySelectorAll('.route-arrow')];
    V.labelsOf = new Map([...svg.querySelectorAll('.destination')].map(g => [Number(g.dataset.index), g]));
    ensureControls(svg);
    renderLegend(ctx);
    apply();
    return points;
  }

  function build(ctx, points) {
    const ds = ctx.destinations, n = ds.length, mode = ctx.view;
    const results = ctx.results || [];
    const focus = results.find(r => r.id === mode);
    const line = (p, q, cls, extra = '') => `<line class="${cls}" x1="${p.x.toFixed(3)}" y1="${p.y.toFixed(3)}" x2="${q.x.toFixed(3)}" y2="${q.y.toFixed(3)}"${extra}/>`;
    let under = '', arrows = '', markers = '';
    if (ctx.showEdges && n <= 50)
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++)
        under += line(points[i], points[j], 'graph-edge', ` data-edge-from="${i}" data-edge-to="${j}"`);
    // Others dimmed (drawn first, non-interactive), then the focused/all routes.
    if (mode !== 'none') for (const r of results) {
      const dim = mode !== 'all' && r.id !== mode;
      for (let step = 1; step < r.route.length; step++) {
        const a = r.route[step - 1], b = r.route[step];
        if (a === b) continue;
        const p = points[a], q = points[b];
        if (dim) { under += line(p, q, `route-path ${r.id} dim`); continue; }
        const text = ctx.legDescription(r, step);
        under += `<g class="route-segment" data-leg="${step}" data-algorithm="${r.id}" tabindex="0" role="button" aria-label="${esc(text)}"><title>${esc(text)}</title>${line(p, q, `route-path ${r.id}`)}${line(p, q, 'route-hit')}</g>`;
        const mid = { x: (p.x + q.x) / 2, y: (p.y + q.y) / 2 };
        arrows += `<path class="route-arrow ${r.id}" data-wx="${mid.x.toFixed(3)}" data-wy="${mid.y.toFixed(3)}" data-angle="${G.angleDegrees(p.x, p.y, q.x, q.y).toFixed(1)}" data-len="${Math.hypot(q.x - p.x, q.y - p.y).toFixed(4)}" d="M-5,-4.5L5,0L-5,4.5Z"/>`;
      }
    }
    // Customers not visited: by the focused route, or by every route when all are shown.
    let skipped = new Set();
    if (focus) skipped = new Set(focus.skipped);
    else if (mode === 'all' && results.length) {
      const sets = results.map(r => new Set(r.skipped));
      skipped = new Set([...sets[0]].filter(i => sets.every(s => s.has(i))));
    }
    const order = focus ? new Map(focus.route.map((v, i) => [v, i])) : null;
    const badge = (i) => focus && i !== 0 && order.get(i) >= 1;
    ds.forEach((d, i) => {
      const p = points[i], isDepot = i === 0, sel = ctx.selected === i;
      const status = ctx.status(i), isSkipped = !isDepot && skipped.has(i);
      const cls = `destination${isDepot ? ' depot' : ''}${status ? ` status-${status.toLowerCase()}` : ''}${sel ? ' selected' : ''}${isSkipped ? ' skipped' : ''}`;
      const shape = isDepot ? '<rect class="depot-shape" x="-12" y="-12" width="24" height="24" rx="5"/><text class="depot-letter" y="4" text-anchor="middle">D</text>'
        : `<circle r="${isSkipped ? 5 : 6.5}"/>${isSkipped ? '<path class="skip-x" d="M-2.6,-2.6L2.6,2.6M-2.6,2.6L2.6,-2.6"/>' : ''}`;
      const aria = ctx.pointAria(i, isSkipped);
      markers += `<g class="${cls}" data-index="${i}" data-wx="${p.x.toFixed(3)}" data-wy="${p.y.toFixed(3)}" tabindex="0" role="button" aria-pressed="${sel}" aria-label="${esc(aria)}"><title>${esc(ctx.pointTitle(i, isSkipped))}</title>${sel ? '<circle class="sel-ring" r="12"/>' : ''}${shape}<text class="point-label" data-full="${esc(d.name)}">${esc(shortName(d.name))}</text></g>`;
      if (badge(i)) markers += `<g class="route-stop" pointer-events="none" data-wx="${p.x.toFixed(3)}" data-wy="${p.y.toFixed(3)}" data-ox="9" data-oy="-9"><circle r="8.5"/><text class="route-order" y="3.4" text-anchor="middle">${order.get(i)}</text></g>`;
    });
    return `<title>Map of input destinations in true proportions (longitude scaled by cosine of latitude). Route overlays show direct travel, not roads.</title>`
      + `<g id="map-viewport">${under}<line id="measurement-line" class="measurement-line" visibility="hidden"/></g>`
      + `<g id="map-screen"><g id="map-arrows" pointer-events="none">${arrows}</g>${markers}</g>`
      + '<g id="map-scale" pointer-events="none"><line class="scale-line" y1="0" y2="0"/><line class="scale-tick a" y1="-4" y2="4"/><line class="scale-tick b" y1="-4" y2="4"/><text class="scale-text" y="-8"></text></g>';
  }

  function apply() {
    const svg = V.svg; if (!svg || !V.view) return;
    const v = V.view, vp = svg.querySelector('#map-viewport');
    if (!vp) return;
    vp.setAttribute('transform', `translate(${v.tx.toFixed(2)} ${v.ty.toFixed(2)}) scale(${v.k})`);
    for (const el of V.markers) {
      const x = el.dataset.wx * v.k + v.tx + (+el.dataset.ox || 0), y = el.dataset.wy * v.k + v.ty + (+el.dataset.oy || 0);
      el.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
    }
    for (const el of V.arrows) {
      const x = el.dataset.wx * v.k + v.tx, y = el.dataset.wy * v.k + v.ty;
      const visible = el.dataset.len * v.k >= ARROW_MIN_PX;
      el.setAttribute('transform', `translate(${x.toFixed(1)} ${y.toFixed(1)}) rotate(${el.dataset.angle})`);
      el.style.display = visible ? '' : 'none';
    }
    placeAllLabels();
    updateScale();
    svg.dispatchEvent(new CustomEvent('mapview', { detail: { zoom: v.k / V.fit.k } }));
  }

  function placeAllLabels() {
    const v = V.view, ctx = V.ctx, ds = ctx.destinations, [w, h] = V.size.split('x').map(Number);
    const mode = ctx.view, focus = (ctx.results || []).find(r => r.id === mode);
    const stops = focus ? new Set(focus.route) : null;
    const items = ds.map((d, i) => {
      const s = G.toScreen(v, V.points[i]), label = shortName(d.name);
      const priority = i === 0 ? 1000 : ctx.selected === i ? 999 : stops && stops.has(i) ? 500 - i * .001 : 100 - i * .001;
      return { id: i, x: s.x, y: s.y, w: G.textWidth(label), h: 14, r: i === 0 ? 14 : (focus && stops && stops.has(i) ? 15 : 8), priority, force: i === 0 || ctx.selected === i };
    });
    const placement = G.placeLabels(items, w, h);
    for (const [i, g] of V.labelsOf) {
      const text = g.querySelector('.point-label'), at = placement.get(i);
      g.classList.toggle('label-on', !!at);
      if (at) { text.setAttribute('x', at.x); text.setAttribute('y', at.y + 4); text.setAttribute('text-anchor', at.anchor); }
      else { text.setAttribute('x', 12); text.setAttribute('y', -10); text.setAttribute('text-anchor', 'start'); }
    }
  }

  function updateScale() {
    const g = V.svg.querySelector('#map-scale'); if (!g) return;
    const [w, h] = V.size.split('x').map(Number), bar = G.scaleBar(V.view.k, Math.min(150, w * .3));
    g.setAttribute('transform', `translate(14 ${h - 16})`);
    g.querySelector('.scale-line').setAttribute('x2', bar.px.toFixed(1));
    g.querySelector('.scale-tick.a').setAttribute('x1', 0); g.querySelector('.scale-tick.a').setAttribute('x2', 0);
    g.querySelector('.scale-tick.b').setAttribute('x1', bar.px.toFixed(1)); g.querySelector('.scale-tick.b').setAttribute('x2', bar.px.toFixed(1));
    g.querySelector('.scale-text').textContent = bar.label;
  }

  function schedule() {
    if (V.raf) return;
    V.raf = requestAnimationFrame(() => { V.raf = 0; apply(); });
  }
  function size() { const [w, h] = V.size.split('x').map(Number); return { w, h }; }
  function zoomBy(factor, cx, cy) {
    if (!V.view) return;
    const { w, h } = size();
    V.view = G.zoomAt(V.view, V.fit, factor, cx ?? w / 2, cy ?? h / 2); V.touched = true; schedule();
  }
  function pan(dx, dy) { if (!V.view) return; V.view = G.panBy(V.view, dx, dy); V.touched = true; schedule(); }
  function reset() { if (!V.fit) return; V.view = { ...V.fit }; V.touched = false; schedule(); }

  function ensureControls(svg) {
    if (V.controls && svg.parentElement.querySelector('.map-controls')) return;
    const wrap = svg.parentElement;
    wrap.insertAdjacentHTML('beforeend',
      '<div class="map-controls" role="group" aria-label="Map zoom"><button type="button" data-map="in" aria-label="Zoom in" title="Zoom in (+)">+</button><button type="button" data-map="out" aria-label="Zoom out" title="Zoom out (−)">−</button><button type="button" data-map="reset" aria-label="Reset view" title="Reset view (0)">&#8634;</button></div>'
      + '<p id="map-keys" class="map-keys">Scroll to zoom, drag to pan. Keys: arrows pan, + and − zoom, 0 resets.</p>');
    wrap.querySelector('.map-controls').addEventListener('click', event => {
      const b = event.target.closest('[data-map]'); if (!b) return;
      if (b.dataset.map === 'in') zoomBy(1.6); else if (b.dataset.map === 'out') zoomBy(1 / 1.6); else reset();
    });
    V.controls = true;
  }

  function renderLegend(ctx) {
    const host = ctx.legend; if (!host) return;
    const algo = (id, name) => `<button type="button" class="map-legend-route${ctx.view === id ? ' on' : ''}" data-legend-route="${id}" aria-pressed="${ctx.view === id}" title="${ctx.view === id ? 'Show all routes' : `Highlight ${name}`}"><svg width="30" height="10" aria-hidden="true"><line class="route-path ${id}" x1="1" y1="5" x2="29" y2="5"/><path class="route-arrow ${id}" transform="translate(15 5)" d="M-4,-4L4,0L-4,4Z"/></svg>${esc(name)}</button>`;
    host.innerHTML = `<span><i class="lg-depot"></i>Depot</span><span><i class="lg-open"></i>Open</span><span><i class="lg-closed"></i>Closed</span><span><i class="lg-skipped"></i>Skipped</span><span><i class="lg-selected"></i>Selected</span>`
      + ctx.algorithms.map(a => algo(a.id, a.name)).join('')
      + `<span class="map-legend-note">${esc(ctx.timeNote)}</span>`;
  }

  // ---------- Interaction ----------
  function init(svg, legend) {
    let drag = null;
    svg.addEventListener('wheel', event => {
      if (!V.view) return;
      event.preventDefault();
      const r = svg.getBoundingClientRect(), s = svg.viewBox.baseVal.width / r.width;
      const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
      zoomBy(Math.exp(-delta * .0016), (event.clientX - r.left) * s, (event.clientY - r.top) * s);
    }, { passive: false });
    svg.addEventListener('pointerdown', event => {
      if (event.button !== 0 || !V.view) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
      V.dragged = false;
    });
    svg.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < CLICK_SLOP) return;
      if (!drag.moved) { drag.moved = true; V.dragged = true; svg.setPointerCapture(event.pointerId); svg.classList.add('panning'); }
      const s = svg.viewBox.baseVal.width / svg.getBoundingClientRect().width;
      pan(dx * s, dy * s); drag.x = event.clientX; drag.y = event.clientY;
      event.stopImmediatePropagation();
    }, true);
    const end = event => {
      if (!drag || drag.id !== event.pointerId) return;
      if (drag.moved && svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
      svg.classList.remove('panning'); drag = null;
      setTimeout(() => { V.dragged = false; }, 0);
    };
    svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
    // A drag must not select a destination or trigger a hover inspection.
    svg.addEventListener('click', event => { if (V.dragged) { event.stopImmediatePropagation(); event.preventDefault(); } }, true);
    svg.addEventListener('keydown', event => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const step = 60, key = event.key;
      const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
      if (moves[key]) { event.preventDefault(); pan(...moves[key]); }
      else if (key === '+' || key === '=') { event.preventDefault(); zoomBy(1.4); }
      else if (key === '-' || key === '_') { event.preventDefault(); zoomBy(1 / 1.4); }
      else if (key === '0') { event.preventDefault(); reset(); }
    });
    svg.addEventListener('focusin', event => {
      const g = event.target.closest?.('[data-index]'); if (!g || !V.view) return;
      const { w, h } = size(), s = G.toScreen(V.view, { x: +g.dataset.wx, y: +g.dataset.wy }), r = G.revealPan(s.x, s.y, w, h, 40);
      if (r.dx || r.dy) pan(r.dx, r.dy);
    });
    legend?.addEventListener('click', event => {
      const b = event.target.closest('[data-legend-route]'); if (!b) return;
      const select = document.getElementById('route-view');
      select.value = select.value === b.dataset.legendRoute ? 'all' : b.dataset.legendRoute;
      select.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  root.MapView = { draw, init, reset, zoomBy, pan, state: V };
})(typeof window === 'undefined' ? globalThis : window);
