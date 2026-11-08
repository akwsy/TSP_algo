"""The submission builder (submission/build_submission.py), tested at its public seam: the command
`build_submission.py --out DIR` and the folder it writes. Derived from the experiments registry,
so a new experiment needs no change here. Skips when the builder is absent (the submission copy
itself contains this tests folder but not the builder, and this file is left out of the copy).

Whether the committed submission/G4T1 is up to date is NOT tested (that would fail every
teammate's pull request); run `python3 submission/build_submission.py --check` for that."""
import filecmp
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILDER = REPO / "submission" / "build_submission.py"
if not BUILDER.exists():
    raise unittest.SkipTest("submission/build_submission.py is not present (this is the submission copy)")

sys.path.insert(0, str(REPO))
from harness.experiments import EXPERIMENTS  # noqa: E402

EXCLUDED_NAMES = {".git", ".claude", ".scratch", "results", "instances", "evaluation", "__pycache__",
                  ".DS_Store", "node_modules", "PROJECT_BRIEF.md", "AGENTS.md", "agents",
                  "build_submission.py", "test_submission.py", "output"}


def build(out):
    subprocess.run([sys.executable, str(BUILDER), "--out", str(out)], check=True, cwd=REPO,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


class SubmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.a, cls.b = base / "a", base / "b"
        build(cls.a)
        build(cls.b)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def folders(self):
        return sorted(p for p in (self.a / "experiments").iterdir() if p.is_dir())

    def test_required_top_level_items(self):
        for name in ("README.md", "data", "harness", "algorithms", "site", "tests", "docs", "start.py",
                     "experiments", "run_all_experiments.py"):
            self.assertTrue((self.a / name).exists(), name)
        for name in ("ALGORITHM_SPEC.md", "DESIGN.md", "Project_2627T1.pdf"):
            self.assertTrue((self.a / "docs" / name).is_file(), name)

    def test_one_numbered_labelled_folder_per_experiment_plus_the_full_run(self):
        folders = self.folders()
        self.assertEqual(len(folders), len(EXPERIMENTS) + 1)
        for number, folder in enumerate(folders, start=1):
            self.assertRegex(folder.name, rf"^{number:02d}-[a-z]+(-[a-z]+)+$")
            self.assertTrue((folder / "README.md").is_file())
            self.assertTrue((folder / "run.py").is_file())
        for exp, folder in zip(EXPERIMENTS.values(), folders):
            self.assertIn(f'EXPERIMENT = "{exp.name}"', (folder / "run.py").read_text())
        last = folders[-1]
        self.assertIn("full-run", last.name)
        self.assertIn('EXPERIMENT = "scaling"', (last / "run.py").read_text())
        self.assertIn("--full-run-instances 10", (last / "README.md").read_text())

    def test_readmes_state_the_name_values_and_fixed_settings(self):
        for exp, folder in zip(EXPERIMENTS.values(), self.folders()):
            text = (folder / "README.md").read_text()
            self.assertIn(f"`{exp.name}`", text)
            for v in exp.values:
                self.assertIn(f"{v:g}", text)
            for key, val in exp.fixed.items():
                self.assertIn(f"{key} = {val:g}", text)
            self.assertIn(str(exp.instances_per_size), text)
            self.assertIn("python3 site/serve.py --results", text)

    def test_algorithms_match_the_repo(self):
        repo = sorted(p.name for p in (REPO / "algorithms").iterdir()
                      if p.is_dir() and p.name != "__pycache__")
        got = sorted(p.name for p in (self.a / "algorithms").iterdir() if p.is_dir())
        self.assertEqual(got, repo)
        self.assertTrue((self.a / "algorithms" / "greedy-insertion" / "compare.py").is_file())

    def test_data_files_are_byte_identical(self):
        for f in (REPO / "data").iterdir():
            self.assertTrue(filecmp.cmp(f, self.a / "data" / f.name, shallow=False), f.name)

    def test_nothing_excluded_is_present(self):
        for rel in tree(self.a):
            self.assertFalse(set(Path(rel).parts) & EXCLUDED_NAMES, rel)
            self.assertFalse(rel.endswith(".pyc"), rel)

    def test_build_is_deterministic(self):
        self.assertEqual(tree(self.a), tree(self.b))
        for rel in tree(self.a):
            if (self.a / rel).is_file():
                self.assertEqual((self.a / rel).read_bytes(), (self.b / rel).read_bytes(), rel)

    def test_check_flag_reports_drift_in_words(self):
        r = subprocess.run([sys.executable, str(BUILDER), "--check"], cwd=REPO, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
        self.assertIn(r.returncode, (0, 1))
        self.assertRegex(r.stdout, r"(?i)up to date|differs|missing")


if __name__ == "__main__":
    unittest.main()
