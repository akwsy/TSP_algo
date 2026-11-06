"""Per-algorithm visual identity (site/js/lib/algstyle.js), run under node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parent.parent / "site" / "js" / "lib" / "algstyle.js"


def styles(count):
    script = (f"import {{ algorithmStyle }} from {json.dumps(MODULE.as_uri())};"
              f"console.log(JSON.stringify(Array.from({{length: {count}}}, (_, i) => algorithmStyle(i))));")
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class AlgorithmStyleTest(unittest.TestCase):
    def test_colour_and_dash_pair_is_unique_for_at_least_twelve_algorithms(self):
        pairs = [(s["colorIndex"], s["dash"]) for s in styles(12)]
        self.assertEqual(len(set(pairs)), 12)

    def test_colour_and_dash_and_shape_triple_is_unique_for_twelve(self):
        triples = [(s["colorIndex"], s["dash"], s["shape"]) for s in styles(12)]
        self.assertEqual(len(set(triples)), 12)

    def test_the_six_colour_blind_safe_colours_come_first_and_shapes_vary_after_six(self):
        s = styles(12)
        self.assertEqual([x["colorIndex"] for x in s[:6]], [0, 1, 2, 3, 4, 5])
        self.assertTrue(all(0 <= x["colorIndex"] < 6 for x in s))
        self.assertNotEqual([x["shape"] for x in s[:6]], [x["shape"] for x in s[6:12]])

    def test_deterministic(self):
        self.assertEqual(styles(14), styles(14))


if __name__ == "__main__":
    unittest.main()
