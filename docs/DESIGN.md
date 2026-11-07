# Results website: design direction

A dark, cinematic mission control for comparing routing algorithms. Plain HTML, CSS and JS in `site/`, no build step, no
web fonts or CDNs (Leaflet and its tiles stay optional, with the SVG fallback).

## Look

- **Ground and panels.** Near-black blue page (`--bg #070a0f`), graphite panels (`--surface #0d131b`, raised rows
  `--surface-2 #121a25`) framed by thin lines (`--line`, `--line-strong`) with cyan corner ticks. A faint instrument
  grid sits behind the top of every page and fades out; scan lines appear only at the edges of the map screen.
- **One accent that glows on what is live:** cyan `--accent #5cc8ff` for the current tab, the title rule, chart
  captions, links and hover glows. Focus rings are amber `--focus #ffb547`, 3px, never removed.
- **Status** is always a word plus a small light (`.badge`), in `--ok`, `--warn`, `--bad` on their own tints.
- **Light mode ("daylight console")** keeps the same frames, corner ticks and type on cool paper (`--bg #e9eef4`,
  white panels). Glows become crisp tints: `--glow-r` is 0 in light, so routes, chart lines and figures lose their
  halo but keep their weight.
- **Dark is the default** whatever the OS says. The header button cycles Dark, Light, System (stored in
  `localStorage`, read before first paint by `js/boot.js`).

## Type

System sans for words; system monospace (`--mono`) for every measured number, table heads and control labels.
Scale: 12 / 14 / 16 / 20 px and page titles at `clamp(32px, ..., 52px)`, weight 760, tracking -0.035em, with a
glowing accent rule under them.

## Colour for data

The six series colours `--s1..--s6` and the four opening-time slot colours live in `site/css/charts.css`. They
were kept as they were: they still pass `tests/tools/validate_palette.js` (the dataviz validator) against the new
dark panel surface, and `tests/test_site_contrast.py` checks every text, status, focus, control and slot token
against `bg`, `surface` and `surface-2` in light, dark and system-dark. Map entries use the tokens themselves
(`var(--sN)`), so a theme switch recolours lines, markers and swatches without a redraw.

## Motion

Every animation explains something, finishes quickly, and is decoration over a final state that is already correct.

| Move | What it says | Timing |
| --- | --- | --- |
| A new view assembles panel by panel | what just loaded, top to bottom | 640 ms, 70 ms stagger |
| Ranked rows slide in, figures count up from zero | the ranking order, and that these are measured values | 520 ms rows, 750 ms counts |
| Overview readout counts up | the headline figures for the chosen size | 700 ms |
| Chart lines draw left to right | growth with the number of customers | 900 ms |
| Routes draw leg by leg in visiting order; stops light up when reached; stop numbers pop in; a glowing head leads; a counter reads "stop k of n" | the order the algorithm visits places | up to 3.2 s, skippable |
| Depot beacon pulses twice when a route starts | where every route begins and ends | 2 x 2 s |
| Glowing bar glides to the current tab | where you are | 320 ms |
| Tooltips and details fade and slide in; hover glows on panels, rows and buttons | what you are pointing at | 160-320 ms |

Rules: ease-out, transform and opacity (plus clip-path for chart draw-in), nothing flashes, nothing blocks input.
The route draw-in starts only when the map is on screen, jumps to the end on zoom, pan, resize, fullscreen or
**Skip animation**, and can be replayed with **Replay route**.

`prefers-reduced-motion: reduce` or the header **Reduce motion** toggle (stored in `localStorage`) sets
`data-motion="reduce"` on `<html>`: CSS animations and transitions are switched off, count-ups and the route draw-in
never start, and the Replay button is hidden. The system setting always wins over the toggle.
Timing and the on/off rule are pure functions in `site/js/lib/motion.js`, tested by `tests/test_site_motion.py`.
