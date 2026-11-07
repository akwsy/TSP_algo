// Runs before first paint (plain script in <head>) so the page never flashes the wrong theme or starts an animation it should not.
// Mirrors resolveTheme / motionAllowed in js/lib/motion.js (tested); js/app.js re-applies them with that module.
(function () {
  var root = document.documentElement, theme = null, motion = null;
  try { theme = localStorage.getItem("theme"); motion = localStorage.getItem("motion"); } catch (e) { /* storage blocked */ }
  if (theme !== "light" && theme !== "system") theme = "dark";
  if (theme === "system") root.removeAttribute("data-theme"); else root.setAttribute("data-theme", theme);
  var systemReduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  root.setAttribute("data-motion", !systemReduce && motion !== "reduce" ? "full" : "reduce");
})();
