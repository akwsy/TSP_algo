'use strict';
// UI-only display helpers; routing and feasibility keep their original precision.
(function (root) {
  function clock(minutes, origin = 0) {
    if (!Number.isFinite(minutes) || !Number.isFinite(origin)) return '—';
    const total = Math.floor(minutes + origin + 1e-9), day = Math.floor(total / 1440);
    const today = ((total % 1440) + 1440) % 1440;
    return `${String(Math.floor(today / 60)).padStart(2, '0')}:${String(today % 60).padStart(2, '0')}${day ? ` +${day}d` : ''}`;
  }
  function duration(minutes) {
    if (!Number.isFinite(minutes) || minutes < 0) return '—';
    const total = Math.floor(minutes + 1e-9);
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  }
  function status(index, open, close, time) {
    if (!Number.isFinite(time)) return 'Unknown';
    if (index === 0) return 'Open';
    if (!Number.isFinite(open) || !Number.isFinite(close) || open < 0 || close < 0 || open > close) return 'Unknown';
    return time >= open - 1e-9 && time <= close + 1e-9 ? 'Open' : 'Closed';
  }
  function arrivalAt(result, index) {
    return result?.visits.find(visit => visit.vertex === index)?.arrival ?? null;
  }
  root.Inspection = { clock, duration, status, arrivalAt };
})(typeof window === 'undefined' ? globalThis : window);
