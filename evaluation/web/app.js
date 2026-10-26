'use strict';
const $ = id => document.getElementById(id);
const state = { scenario: null, comparison: null, selected: null, inspectionTime: null, busy: false, hoverKey: null, hoverTarget: null, graphPoints: [] };
const labels = { nearest: 'Nearest neighbour', greedy: 'Greedy insertion', exact: 'Branch and bound' };
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (value, digits = 2) => Number(value).toLocaleString('en', { minimumFractionDigits: digits, maximumFractionDigits: digits });
function clock(minutes, origin = state.scenario?.clockStartMinutes || 0) {
  return Inspection.clock(minutes, origin);
}
const duration = minutes => Inspection.duration(minutes);
function inspectionResult() {
  const choice = $('route-view').value;
  return state.comparison?.results.find(result => result.id === choice)
    || (choice === 'all' ? state.comparison?.results.find(result => result.id === 'nearest') : null);
}
function locationStatus(d, time) {
  const window = destinationWindow(d);
  return Inspection.status(d.index, window.open, window.close, time);
}
function windowText(d) {
  if (d.index === 0) return 'Always open';
  const { open, close } = destinationWindow(d);
  return `${clock(open)}–${clock(close)}`;
}
function updateOriginInfo() {
  if (state.selected === null) return;
  const d = (state.comparison?.scenario || state.scenario).destinations[state.selected];
  const reference = inspectionResult();
  $('origin-info').textContent = `${d.name} · Arrival: ${clock(state.inspectionTime)}${reference ? ` · ${reference.name}` : ''}. Colours show open/closed at this time.`;
}
function syncInspectionTime() {
  if (state.selected === null) return;
  const routeArrival = Inspection.arrivalAt(inspectionResult(), state.selected);
  state.inspectionTime = routeArrival ?? Number($('departure').value);
  updateOriginInfo();
}
function notice(message, error = false) {
  $('notice').hidden = !message; $('notice').textContent = message; $('notice').classList.toggle('error', error);
}
function busy(value, message = '') {
  state.busy = value; document.body.classList.toggle('busy', value);
  document.querySelectorAll('button, input, select').forEach(element => { element.disabled = value; });
  $('download').disabled = value || !state.comparison;
  $('clear-origin').disabled = value || state.selected === null;
  $('show-edges').disabled = value || (state.scenario?.destinations.length || 0) > 50;
  $('run-state').textContent = message || 'Same inputs for every algorithm.';
  $('compare-button').textContent = value ? 'Working…' : 'Compare algorithms';
}
async function api(path, body) {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body } : {});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
function invalidate() {
  if (state.busy) return;
  state.comparison = null; $('download').disabled = true;
  $('results').innerHTML = '<div class="empty-result">Inputs changed. Compare again to calculate fresh routes.</div>';
  $('comparison-summary').textContent = 'Your input changes have not been compared yet.';
  $('run-state').textContent = 'Inputs changed — ready to compare.';
  syncInspectionTime(); drawGraph(); updateClock();
}
function updateClock() {
  $('departure-clock').textContent = `Leaves at ${clock(Number($('departure').value))}`;
}
function setScenario(scenario) {
  state.scenario = scenario; state.comparison = null; state.selected = null;
  $('duration').value = scenario.durationMinutes; $('speed').value = scenario.speedKmh; $('departure').value = 0;
  $('origin-label').textContent = `minutes from ${clock(0).slice(0, 5)}`;
  $('input-origin').textContent = clock(0).slice(0, 5);
  $('network-count').textContent = `${scenario.destinations.length} vertices · ${scenario.edgeCount.toLocaleString()} edges`;
  $('show-edges').checked = false;
  $('show-edges').title = scenario.destinations.length > 50 ? 'Graph connections are hidden above 50 vertices to keep the view responsive.' : '';
  resetOrigin();
  $('input-rows').innerHTML = scenario.destinations.map(d => `<tr><td>${escapeHtml(d.name)}<small>${d.id}${d.index === 0 ? ' · DEPOT' : ''}</small></td>${d.index === 0 ? '<td colspan="2"><span class="depot-tag">Departure only</span></td>' : `<td><input type="number" min="0" step="any" value="${d.opensAt}" data-index="${d.index}" data-bound="opensAt" aria-label="Opening minutes for ${escapeHtml(d.name)}" required></td><td><input type="number" min="0" step="any" value="${d.closesAt}" data-index="${d.index}" data-bound="closesAt" aria-label="Closing minutes for ${escapeHtml(d.name)}" required></td>`}</tr>`).join('');
  $('generate-form').elements.count.value = scenario.destinations.length;
  $('generate-form').elements.depot.value = scenario.destinations[0].id;
  $('generate-form').elements.startClock.value = clock(0).slice(0, 5);
  $('results').innerHTML = '<div class="empty-result">Ready to compare the current scenario.</div>';
  $('comparison-summary').textContent = 'Run a comparison to see route statistics. Expand an algorithm for its full journey.';
  updateClock(); drawGraph();
}
function windowsText() {
  const rows = state.scenario.destinations.map(d => ({ ...d }));
  $('input-rows').querySelectorAll('input').forEach(input => {
    if (!input.reportValidity() || !Number.isFinite(Number(input.value))) throw new Error('Enter finite, nonnegative values for every window.');
    rows[Number(input.dataset.index)][input.dataset.bound] = Number(input.value);
  });
  for (const d of rows) if (d.opensAt > d.closesAt) throw new Error(`The opening time must not exceed the closing time for ${d.name}.`);
  return 'geonameid\topensAt\tclosesAt\n' + rows.map(d => `${d.id}\t${d.opensAt}\t${d.closesAt}`).join('\n');
}
async function compare(event) {
  event?.preventDefault(); if (state.busy || !state.scenario || !$('compare-form').reportValidity()) return;
  try {
    const body = new URLSearchParams(new FormData($('compare-form'))); body.set('windows', windowsText());
    notice(''); busy(true, 'Java is running all three algorithms. Exact search may use its full computation budget.');
    state.comparison = null; $('comparison-summary').textContent = 'Calculating the three routes…'; $('results').innerHTML = '<div class="empty-result">Calculating routes with the Java algorithms…</div>';
    const result = await api('/api/compare', body);
    state.comparison = result; syncInspectionTime(); renderResults(); drawGraph();
    $('run-state').textContent = 'Comparison complete.';
  } catch (error) {
    notice(error.message, true);
    $('comparison-summary').textContent = 'Comparison did not complete.';
    if (!state.comparison) $('results').innerHTML = '<div class="empty-result">The comparison did not complete. Check the inputs and try again.</div>';
  } finally { busy(false, state.comparison ? 'Comparison complete.' : 'Ready when you are.'); }
}
async function reload(autoCompare = false) {
  if (state.busy) return;
  notice(''); busy(true, 'Loading the saved scenario…');
  let loaded = false;
  try { setScenario(await api('/api/scenario')); loaded = true; }
  catch (error) { notice(error.message + ' Use the dataset controls or CLI to load a valid scenario.', true); }
  finally { busy(false); }
  if (loaded && autoCompare) await compare();
}
async function generate(event) {
  event.preventDefault(); if (state.busy || !$('generate-form').reportValidity() || !$('compare-form').reportValidity()) return;
  const body = new URLSearchParams(new FormData($('generate-form')));
  body.set('speedKmh', $('speed').value); body.set('durationMinutes', $('duration').value);
  notice(''); busy(true, 'Selecting records from MY.txt and replacing the saved scenario…');
  try {
    setScenario(await api('/api/generate', body));
    notice(`Saved dataset replaced: ${state.scenario.destinations.length} destinations including depot. New simulated windows are loaded. Compare to see the routes.`);
  } catch (error) { notice(error.message, true); }
  finally { busy(false); }
}
function drawGraph() {
  const scenario = state.comparison?.scenario || state.scenario;
  if (!scenario) return;
  const destinations = scenario.destinations, n = destinations.length, svg = $('network');
  $('graph-empty').hidden = true;
  const width = Math.max(420, Math.min(1000, svg.clientWidth * 1.3));
  const left = 65, right = width - 40, screenCenter = (left + right) / 2;
  const compact = svg.clientWidth < 520;
  svg.setAttribute('viewBox', `0 0 ${width} 480`);
  const latitudes = destinations.map(d => d.latitude), longitudes = destinations.map(d => d.longitude);
  const midLat = (Math.min(...latitudes) + Math.max(...latitudes)) / 2;
  const cos = Math.max(.001, Math.cos(midLat * Math.PI / 180));
  const xs = longitudes.map(x => x * cos), ys = latitudes;
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const scale = Math.min((right - left - 35) / Math.max(maxX - minX, .00001), 330 / Math.max(maxY - minY, .00001));
  const centerX = (minX + maxX) / 2, centerY = (minY + maxY) / 2;
  const points = destinations.map(d => [screenCenter + (d.longitude * cos - centerX) * scale, 230 - (d.latitude - centerY) * scale]);
  state.graphPoints = points; hideHover();
  let content = '<title>Input destinations plotted by longitude and latitude. Route overlays represent direct travel.</title>';
  for (let tick = 0; tick <= 5; tick++) { const x = left + (right - left) * tick / 5; content += `<line class="graph-grid" x1="${x}" y1="35" x2="${x}" y2="425"/><text class="axis-label" x="${x}" y="453" text-anchor="middle">${fmt(((x - screenCenter) / scale + centerX) / cos, 3)}° E</text>`; }
  for (let y = 35; y <= 425; y += 97.5) content += `<line class="graph-grid" x1="${left}" y1="${y}" x2="${right}" y2="${y}"/><text class="axis-label" x="57" y="${y + 3}" text-anchor="end">${fmt(centerY - (y - 230) / scale, 3)}° N</text>`;
  if ($('show-edges').checked && n <= 50) for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++)
    content += `<line class="graph-edge" data-edge-from="${i}" data-edge-to="${j}" x1="${points[i][0]}" y1="${points[i][1]}" x2="${points[j][0]}" y2="${points[j][1]}"/>`;
  const view = $('route-view').value;
  for (const result of state.comparison?.results || []) if (view === 'all' || view === result.id) {
    for (let step = 1; step < result.route.length; step++) {
      const from = result.route[step - 1], to = result.route[step];
      if (from === to) continue;
      const [x1, y1] = points[from], [x2, y2] = points[to], visit = result.visits[step];
      const description = `${result.name}: ${destinations[from].name} to ${destinations[to].name}, ${fmt(visit.legDistanceKm)} km, ${duration(visit.legTravelMinutes)} travel time`;
      content += `<g class="route-segment" data-leg="${step}" data-algorithm="${result.id}" tabindex="0" role="button" aria-label="${escapeHtml(description)}"><title>${escapeHtml(description)}</title><line class="route-path ${result.id}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/><line class="route-hit" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/></g>`;
    }
  }
  content += '<line id="measurement-line" class="measurement-line" visibility="hidden"/>';
  const selectedResult = state.comparison?.results.find(r => r.id === view);
  destinations.forEach((d, i) => {
    const [x, y] = points[i], selected = state.selected === i;
    const window = windowText(d);
    const status = state.selected === null ? '' : locationStatus(d, state.inspectionTime);
    content += `<g class="destination${i === 0 ? ' depot' : ''}${status ? ` status-${status.toLowerCase()}` : ''}${selected ? ' selected' : ''}" data-index="${i}" tabindex="0" role="button" aria-pressed="${selected}" aria-label="${escapeHtml(d.name)}, ${escapeHtml(window)}${status ? `, ${status.toLowerCase()} at ${clock(state.inspectionTime)}` : ""}${selected ? ", selected location" : ""}"><title>${escapeHtml(d.name)} · ${escapeHtml(window)}${status ? ` · ${status}` : ""}</title><circle cx="${x}" cy="${y}" r="${i === 0 ? 12 : 6}"/>`;
    if (i === 0) content += `<text class="depot-letter" x="${x}" y="${y + 3.5}" text-anchor="middle">D</text>`;
    if ((!compact && n <= 25) || selected || i === 0) content += `<text class="point-label" x="${x + 12}" y="${y - 11}">${escapeHtml(d.name)}</text>`;
    content += '</g>';
    if (selectedResult && i !== 0) {
      const order = selectedResult.route.indexOf(i);
      if (order >= 1) content += `<circle class="route-stop" pointer-events="none" cx="${x - 10}" cy="${y + 12}" r="9"/><text class="route-order" pointer-events="none" x="${x - 10}" y="${y + 15}" text-anchor="middle">${order}</text>`;
    }
  });
  svg.innerHTML = content;
}
function resetOrigin() {
  state.selected = null; state.inspectionTime = null; hideHover();
  $('origin-info').textContent = 'Click a destination to set the current location and time, then hover to inspect.';
  $('point-info').textContent = 'Click a destination first. Hover details will appear here and beside the pointer.';
  $('clear-origin').disabled = true;
}
function selectPoint(index) {
  const scenario = state.comparison?.scenario || state.scenario;
  const arrival = Inspection.arrivalAt(inspectionResult(), index);
  let time = Number($('departure').value);
  const speed = Number($('speed').value);
  if (arrival !== null) time = arrival;
  else if (state.selected !== null && scenario.distanceKm && Number.isFinite(speed) && speed > 0)
    time = state.inspectionTime + scenario.distanceKm[state.selected][index] * 60 / speed;
  state.selected = index; state.inspectionTime = time;
  updateOriginInfo();
  $('point-info').textContent = 'Hover over a destination or route for distance, time, departure, arrival and opening hours.';
  $('clear-origin').disabled = state.busy;
  drawGraph();
}
function hideHover() {
  state.hoverKey = null; state.hoverTarget = null;
  $('graph-tooltip').hidden = true;
  $('measurement-line')?.setAttribute('visibility', 'hidden');
}
function destinationWindow(d) {
  return {
    open: Number($('input-rows').querySelector(`[data-index="${d.index}"][data-bound="opensAt"]`)?.value ?? d.opensAt),
    close: Number($('input-rows').querySelector(`[data-index="${d.index}"][data-bound="closesAt"]`)?.value ?? d.closesAt)
  };
}
function conciseTrip(from, to, distance, travel, departure, arrival) {
  return `${from.name} → ${to.name}\nDistance: ${fmt(distance)} km\nTime taken: ${duration(travel)}\nDeparture: ${clock(departure)}\nArrival: ${clock(arrival)}\nWindow: ${windowText(to)}\n${locationStatus(to, arrival)}`;
}
function hoverText(target) {
  const scenario = state.comparison?.scenario || state.scenario;
  if (!scenario) return '';
  const destinations = scenario.destinations;
  if (state.selected === null) return 'Click a destination first to select the current location.';
  if (!scenario.distanceKm) return 'Restart the UI server and reload this page to load distance measurements.';
  if (target.hasAttribute('data-leg')) {
    const result = state.comparison?.results.find(r => r.id === target.dataset.algorithm);
    if (!result) return '';
    const step = Number(target.dataset.leg), visit = result.visits[step];
    const from = destinations[result.route[step - 1]], to = destinations[visit.vertex];
    return conciseTrip(from, to, visit.legDistanceKm, visit.legTravelMinutes,
      result.visits[step - 1].visitTime, visit.arrival);
  }
  let fromIndex = state.selected, toIndex;
  if (target.hasAttribute('data-index')) toIndex = Number(target.dataset.index);
  else {
    const a = Number(target.dataset.edgeFrom), b = Number(target.dataset.edgeTo);
    fromIndex = state.selected === b ? b : a; toIndex = fromIndex === a ? b : a;
  }
  const from = destinations[fromIndex], to = destinations[toIndex], speed = Number($('speed').value);
  if (!Number.isFinite(speed) || speed <= 0) return 'Enter a positive travel speed.';
  const distance = scenario.distanceKm[fromIndex][toIndex], travel = distance * 60 / speed;
  const departure = state.inspectionTime, arrival = departure + travel;
  const line = $('measurement-line'), fromPoint = state.graphPoints[fromIndex], toPoint = state.graphPoints[toIndex];
  if (line && fromPoint && toPoint) {
    for (const [key, value] of Object.entries({ x1: fromPoint[0], y1: fromPoint[1], x2: toPoint[0], y2: toPoint[1] })) line.setAttribute(key, value);
    line.setAttribute('visibility', 'visible');
  }
  return conciseTrip(from, to, distance, travel, departure, arrival);
}
function inspectHover(target, event) {
  if (!target || !state.scenario || state.busy) { hideHover(); return; }
  const key = target.dataset.index !== undefined ? `point:${target.dataset.index}` : target.dataset.leg !== undefined ? `leg:${target.dataset.algorithm}:${target.dataset.leg}` : `edge:${target.dataset.edgeFrom}:${target.dataset.edgeTo}`;
  const tooltip = $('graph-tooltip');
  if (key !== state.hoverKey) {
    $('measurement-line')?.setAttribute('visibility', 'hidden');
    const text = hoverText(target);
    if (!text) { hideHover(); return; }
    tooltip.textContent = text; $('point-info').textContent = text;
    state.hoverKey = key;
  }
  state.hoverTarget = target;
  tooltip.hidden = false;
  const bounds = target.getBoundingClientRect();
  const x = event?.clientX ?? bounds.right, y = event?.clientY ?? bounds.top;
  const width = tooltip.offsetWidth, height = tooltip.offsetHeight;
  tooltip.style.left = `${Math.max(8, Math.min(x + 14, window.innerWidth - width - 8))}px`;
  tooltip.style.top = `${Math.max(8, Math.min(y + 14, window.innerHeight - height - 8))}px`;
}
function renderResults() {
  const comparison = state.comparison, scenario = comparison.scenario, candidates = scenario.customerCount;
  const baseline = comparison.results[0].visitedCount;
  const best = [...comparison.results].sort((a, b) => b.visitedCount - a.visitedCount || a.distanceKm - b.distanceKm)[0];
  const exact = comparison.results.find(r => r.id === 'exact');
  $('comparison-summary').textContent = `Best observed: ${best.name}, ${best.visitedCount}/${candidates} customers. ${exact.status === 'OPTIMAL' ? 'Exact search proved the maximum count and the shortest distance for that count.' : 'Exact search reached a limit; maximum visit count is not proved.'} Expand a row for the route.`;
  $('results').innerHTML = comparison.results.map(result => {
    const gain = result.visitedCount - baseline;
    const kind = result.baseline ? 'Baseline' : `${result.id === 'exact' ? 'Exact search' : 'Insertion heuristic'} · ${result.status === 'SEARCH_LIMIT_REACHED' ? 'limit reached' : `${gain >= 0 ? '+' : ''}${gain} visits vs baseline`}`;
    const outcome = result.status === 'OPTIMAL' ? 'Proven optimal' : result.status === 'SEARCH_LIMIT_REACHED' ? 'Search limit reached' : 'Feasible heuristic';
    const metrics = [
      ['Customers visited', `<span class="metric-value count">${result.visitedCount}<small> / ${candidates}</small></span>`],
      ['Distance', `<span class="metric-value">${fmt(result.distanceKm)} <small>km</small></span>`],
      ['Waiting', `<span class="metric-value">${duration(result.waitingMinutes)}</span>`],
      ['Return time', `<span class="metric-value">${clock(result.finishTime)}</span>`],
      ['Computation', `<span class="metric-value">${fmt(result.elapsedMs)} <small>ms</small></span>`]
    ];
    const sequence = result.route.map(i => escapeHtml(scenario.destinations[i].name)).join('<span>→</span>');
    const rows = result.visits.map((visit, order) => {
      const d = scenario.destinations[visit.vertex], returning = order === result.visits.length - 1;
      const window = visit.vertex === 0 ? (returning ? `By ${clock(comparison.deadline)}` : 'Departure') : `${clock(d.opensAt)}–${clock(d.closesAt)}`;
      const departure = order === 0 ? visit.arrival : result.visits[order - 1].visitTime;
      return `<tr class="${returning ? 'return-row' : ''}"><td>${order}</td><td>${escapeHtml(d.name)}${returning ? ' · return' : ''}<br><small>${d.id}</small></td><td>${fmt(visit.legDistanceKm)} km</td><td>${duration(visit.legTravelMinutes)}</td><td>${clock(departure)}</td><td>${clock(visit.arrival)}</td><td>${window}</td><td>${locationStatus(d, visit.arrival)}</td></tr>`;
    }).join('');
    const skipped = result.skipped.length ? result.skipped.map(i => `${escapeHtml(scenario.destinations[i].name)} (${scenario.destinations[i].id})`).join(', ') : 'None — every customer was visited.';
    return `<details class="algorithm ${result.id}" data-algorithm="${result.id}"><summary><div><span class="algo-title">${escapeHtml(result.name)}</span><span class="algo-kind">${kind}</span></div>${metrics.map(([label, value]) => `<div class="metric"><span class="metric-label">${label}</span>${value}</div>`).join('')}<span class="chevron">Route details</span></summary><div class="route-details"><div class="detail-heading"><p class="outcome"><strong>${outcome}.</strong> ${escapeHtml(result.message)}</p><button class="button secondary small" type="button" data-show-route="${result.id}">Show on graph</button></div><div class="detail-stats"><span>Computation: <strong>${fmt(result.elapsedMs)} ms</strong></span><span>Travel: <strong>${duration(result.travelMinutes)}</strong></span><span>Waiting: <strong>${duration(result.waitingMinutes)}</strong></span><span>Used: <strong>${duration(result.finishTime - comparison.startTime)} / ${duration(comparison.durationMinutes)}</strong></span><span>Remaining: <strong>${duration(Math.max(0, comparison.deadline - result.finishTime))}</strong></span><span>${result.id === 'exact' ? 'Search states' : 'Candidate checks'}: <strong>${result.workCount.toLocaleString()}</strong></span></div><p class="route-sequence">${sequence}</p><div class="route-table-wrap"><table class="route-table"><thead><tr><th>Step</th><th>Destination</th><th>Leg distance</th><th>Time taken</th><th>Departure</th><th>Arrival</th><th>Window / deadline</th><th>Status at arrival</th></tr></thead><tbody>${rows}</tbody></table></div><p class="skipped"><strong>Skipped:</strong> ${skipped}</p></div></details>`;
  }).join('');
  $('download').disabled = false;
}
$('compare-form').addEventListener('submit', compare);
$('generate-form').addEventListener('submit', generate);
$('reload').addEventListener('click', () => reload(false));
$('compare-form').addEventListener('input', invalidate);
$('input-rows').addEventListener('input', invalidate);
$('route-view').addEventListener('change', () => { syncInspectionTime(); drawGraph(); });
$('show-edges').addEventListener('change', drawGraph);
const graphTarget = event => event.target.closest('[data-index], [data-leg], [data-edge-from]');
$('network').addEventListener('click', event => {
  const point = event.target.closest('[data-index]');
  if (point) selectPoint(Number(point.dataset.index));
  else inspectHover(graphTarget(event), event);
});
$('network').addEventListener('pointermove', event => inspectHover(graphTarget(event), event));
$('network').addEventListener('pointerleave', hideHover);
$('network').addEventListener('focusin', event => inspectHover(graphTarget(event)));
$('network').addEventListener('focusout', hideHover);
$('network').addEventListener('keydown', event => {
  if (event.key === 'Escape') { hideHover(); return; }
  if (event.key === 'Enter' || event.key === ' ') {
    const point = event.target.closest('[data-index]');
    if (point) {
      event.preventDefault(); const index = Number(point.dataset.index); selectPoint(index);
      $('network').querySelector(`[data-index="${index}"]`)?.focus();
    }
  }
});
$('clear-origin').addEventListener('click', () => { resetOrigin(); drawGraph(); });
window.addEventListener('scroll', () => {
  const target = state.hoverTarget;
  if (!target || !target.isConnected) { hideHover(); return; }
  const bounds = target.getBoundingClientRect();
  if (bounds.bottom < 0 || bounds.top > window.innerHeight) hideHover();
  else inspectHover(target);
}, true);
$('results').addEventListener('click', event => {
  const button = event.target.closest('[data-show-route]');
  if (button) { $('route-view').value = button.dataset.showRoute; syncInspectionTime(); drawGraph(); $('network').scrollIntoView({ behavior: 'smooth', block: 'center' }); }
});
$('download').addEventListener('click', () => {
  if (!state.comparison) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.comparison, null, 2)], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'route-comparison.json'; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
reload(true);

new ResizeObserver(() => drawGraph()).observe($('network').parentElement);
