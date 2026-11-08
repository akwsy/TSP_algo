"""WCAG contrast of the site's real CSS tokens: links, map badges, opening-time (slot) colours, in both themes."""
import re
import unittest
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "site" / "css"
TOKEN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})")


def strip(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def rule(css, selector):
    """Token -> hex from the first rule block whose selector text is exactly `selector` (also inside @media)."""
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", strip(css)):
        if sel.strip() == selector:
            return {k: v.lower() for k, v in TOKEN.findall(body)}
    raise AssertionError(f"no rule {selector!r}")


def lum(hexcol):
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def themes():
    style, charts = (CSS / "style.css").read_text(), (CSS / "charts.css").read_text()
    out = {}
    for name, sel in (("light", ":root"), ("dark", ':root[data-theme="dark"]'), ("system-dark", ':root:not([data-theme="light"])')):
        out[name] = {**rule(style, sel), **rule(charts, sel)}
        if name == "light":
            out[name].update({k: v for k, v in {**rule(charts, sel)}.items()})
    return out


class ContrastTest(unittest.TestCase):
    def setUp(self):
        self.t = themes()

    def test_color_scheme_follows_theme(self):
        style = strip((CSS / "style.css").read_text())
        self.assertRegex(style, r":root\s*\{[^}]*color-scheme:\s*light;")
        self.assertRegex(style, r':root:not\(\[data-theme="light"\]\)\s*\{[^}]*color-scheme:\s*dark;')  # system dark
        self.assertRegex(style, r':root\[data-theme="light"\]\s*\{[^}]*color-scheme:\s*light\b')
        self.assertRegex(style, r':root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark\b')

    def test_links_and_skip_link_have_explicit_accessible_colours(self):
        style = strip((CSS / "style.css").read_text())
        self.assertRegex(style, r"(^|\})\s*a\s*\{[^}]*color:\s*var\(--accent\)")
        self.assertRegex(style, r"\.skip\s*\{[^}]*color:\s*var\(--text\)")
        for name, t in self.t.items():
            for bg in ("surface", "bg"):
                self.assertGreaterEqual(ratio(t["accent"], t[bg]), 4.5, f"link on {bg} ({name})")
                self.assertGreaterEqual(ratio(t["text"], t[bg]), 4.5, f"text on {bg} ({name})")

    def test_secondary_text_status_focus_and_controls_on_every_surface(self):
        # Mission control surfaces: page (bg), panel (surface) and raised panel/header rows (surface-2).
        for name, t in self.t.items():
            for bg in ("surface", "surface-2", "bg"):
                for fg in ("muted", "ok", "warn", "bad", "accent"):
                    self.assertGreaterEqual(ratio(t[fg], t[bg]), 4.5, f"{fg} on {bg} ({name})")
                self.assertGreaterEqual(ratio(t["focus"], t[bg]), 3.0, f"focus ring on {bg} ({name})")
                self.assertGreaterEqual(ratio(t["control"], t[bg]), 3.0, f"control border on {bg} ({name})")
            for fg in ("ok", "warn", "bad"):  # status badges sit on their own tint
                self.assertGreaterEqual(ratio(t[fg], t[f"{fg}-bg"]), 4.5, f"{fg} badge ({name})")

    def test_stop_number_badges_read_at_4_5(self):
        css = strip((CSS / "map.css").read_text())
        self.assertRegex(css, r"\.lf-badge\s*\{[^}]*background:\s*var\(--surface\)[^}]*color:\s*var\(--text\)")
        self.assertRegex(css, r"\.badge-t\s*\{[^}]*fill:\s*var\(--text\)")
        for name, t in self.t.items():
            self.assertGreaterEqual(ratio(t["text"], t["surface"]), 4.5, name)
            for i in range(1, 7):  # the ring that carries the series colour is a graphic: 3:1
                self.assertGreaterEqual(ratio(t[f"s{i}"], t["surface"]), 3.0, f"s{i} ring {name}")

    def test_slot_colours_are_3_to_1_against_surface_and_page_in_both_themes(self):
        for name, t in self.t.items():
            vals = [t[f"slot-{i}"] for i in range(1, 5)]
            self.assertEqual(len(set(vals)), 4)
            for i, c in enumerate(vals, 1):
                for bg in ("surface", "bg"):
                    self.assertGreaterEqual(ratio(c, t[bg]), 3.0, f"slot-{i} {c} on {bg} ({name})")


if __name__ == "__main__":
    unittest.main()
