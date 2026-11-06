# T5: Improve the map
Scope: NEW `evaluation/web/map.js`, `map.css`; replace the graph drawing section of `evaluation/web/app.js` with calls into it; add the two files to the served list in `evaluation/src/evaluation/app/UiServer.java` (staticFile switch) and the `<script>/<link>` tags in `index.html`. Do not restyle the rest of the page (T4 owns it).

The current map is a plain SVG scatter plot. Improve it, fully offline (no tiles, no libraries):
- Correct geographic aspect ratio (scale longitude by cos(latitude)); fit-to-bounds with padding.
- Zoom and pan (wheel, drag, +/- buttons, reset), keyboard accessible.
- Routes drawn with direction arrows and numbered stops; the selected algorithm highlighted, others dimmed; per-algorithm colours kept.
- Clear depot marker; open/closed state at the chosen time; skipped customers visually distinct.
- Labels that avoid overlap (show on hover/focus or when zoomed in); a tooltip with name, window, arrival, wait.
- Scale bar in km; legend.
- Works for 10 to 200 destinations without lag.
Tests: pure geometry helpers (projection, bounds, label placement) in a Node test like `evaluation/tests/inspection.test.cjs`. Keep existing element ids used by tests.
