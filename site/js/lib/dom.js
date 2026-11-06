// Tiny DOM helpers. Text is always set via textContent, never innerHTML.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const fmt = (x, digits = 1) =>
  typeof x === "number" ? x.toLocaleString("en", { maximumFractionDigits: digits, minimumFractionDigits: digits }) : "n/a";

export function select(label, options, value, onchange) {
  const sel = h("select", { onchange: (e) => onchange(e.target.value) },
    options.map((o) => h("option", { value: o.value, selected: String(o.value) === String(value) }, o.label)));
  return h("label", {}, label, sel);
}
