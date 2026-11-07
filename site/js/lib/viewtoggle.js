// The header toggle: a two-option radio group ("First day only" / "Until every place is visited").
// Arrow keys move and select (Home/End too); Tab enters and leaves the group once (roving tabindex); Space and Enter select.
// It only calls setView() from lib/view.js and listens to its event, so it never knows about pages.
import { h } from "./dom.js";
import { VIEWS, viewLabel, viewAfterKey, getView, setView, onViewChange } from "./view.js";

/** Build the group into `container`. `counts` is { first: "30 examples per size", full: "..." } (may be filled in later via the returned update()). */
export function mountViewToggle(container) {
  const buttons = new Map();
  const group = h("div", { class: "viewswitch", role: "radiogroup", "aria-label": "Which results to show" });
  for (const id of VIEWS) {
    const count = h("small", { class: "view-count" });
    const btn = h("button", { type: "button", class: "view-opt", role: "radio", "data-view": id,
      onclick: () => setView(id),
      onkeydown: (e) => {
        const next = viewAfterKey(id, e.key);
        if (!next) return;
        e.preventDefault();
        setView(next);
        buttons.get(next).btn.focus();
      } }, h("span", { class: "view-name" }, viewLabel(id)), count);
    buttons.set(id, { btn, count });
    group.append(btn);
  }
  const sync = (view = getView()) => {
    for (const [id, { btn }] of buttons) {
      btn.setAttribute("aria-checked", String(id === view));
      btn.tabIndex = id === view ? 0 : -1;
    }
  };
  sync();
  onViewChange(sync);
  container.replaceChildren(group);
  return {
    /** Fill in the instance-count line under each option. */
    setCounts(counts) {
      for (const [id, { count }] of buttons) count.textContent = counts?.[id] || "";
    },
  };
}
