"""The site's series palette (--s1..--s6 in site/css/charts.css) must pass the dataviz validator in both themes."""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

SITE_CSS = Path(__file__).resolve().parent.parent / "site" / "css"
VALIDATOR = Path(__file__).resolve().parent / "tools" / "validate_palette.js"  # vendored from the dataviz skill
DECL = re.compile(r"--(s[1-6]|surface):\s*(#[0-9a-fA-F]{6})")


def declarations(css, selector):
    """Token -> hex from the first rule block whose selector text is exactly `selector`."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if sel.strip() == selector:
            return {k: v.lower() for k, v in DECL.findall(body)}
    raise AssertionError(f"no rule {selector!r}")


def series(tokens):
    return ",".join(tokens[f"s{i}"] for i in range(1, 7))


def run_validator(palette, mode, surface):
    return subprocess.run(["node", str(VALIDATOR), palette, "--mode", mode, "--surface", surface],
                          capture_output=True, text=True)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class SeriesPaletteTest(unittest.TestCase):
    def setUp(self):
        charts = (SITE_CSS / "charts.css").read_text()
        style = (SITE_CSS / "style.css").read_text()
        self.light = declarations(charts, ":root")
        self.dark = declarations(charts, ':root[data-theme="dark"]')
        self.dark_auto = declarations(charts, ':root:not([data-theme="light"])')
        self.surface_light = declarations(style, ":root")["surface"]
        self.surface_dark = declarations(style, ':root[data-theme="dark"]')["surface"]

    def check(self, tokens, mode, surface):
        r = run_validator(series(tokens), mode, surface)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("[WARN]", r.stdout, r.stdout)
        self.assertNotIn("[FAIL]", r.stdout, r.stdout)

    def test_light_palette_passes_every_check(self):
        self.check(self.light, "light", self.surface_light)

    def test_dark_palette_passes_every_check(self):
        self.check(self.dark, "dark", self.surface_dark)

    def test_system_dark_rule_matches_explicit_dark_rule(self):
        self.assertEqual(self.dark, self.dark_auto)


if __name__ == "__main__":
    unittest.main()
