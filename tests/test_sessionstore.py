"""Session store: saving finds its own older files through the index, never by reading others."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness.sessionstore import read_sessions_index, save_session


def session(alg="alpha", inst="n2-seed1", run="R1", fingerprint="fp", **extra):
    return {"algorithmId": alg, "instanceId": inst, "runId": run, "fingerprint": fingerprint,
            "instanceHash": "hash-" + inst, "experiment": "scaling", "formatVersion": 1, "maxDays": 30,
            "outcome": "finished", "days": 2, **extra}


class SaveSessionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.results = Path(tmp.name)
        (self.results / "sessions").mkdir()

    def files(self):
        return sorted(p.name for p in (self.results / "sessions").glob("*.json"))

    def test_saving_again_replaces_the_older_file_and_entry_of_the_same_key(self):
        entries = save_session(self.results, [], session(run="R1"))
        entries = save_session(self.results, entries, session(run="R2"))
        self.assertEqual(self.files(), ["alpha__n2-seed1__R2.json"])
        self.assertEqual([e["runId"] for e in entries], ["R2"])
        self.assertEqual(read_sessions_index(self.results), entries)

    def test_other_versions_and_other_instances_are_kept(self):
        entries = save_session(self.results, [], session(run="R1", fingerprint="old"))
        entries = save_session(self.results, entries, session(run="R2", fingerprint="new"))
        entries = save_session(self.results, entries, session(run="R2", inst="n2-seed2"))
        self.assertEqual(len(self.files()), 3)
        self.assertEqual(len(entries), 3)

    def test_unindexed_leftovers_of_the_same_algorithm_and_instance_are_removed(self):
        (self.results / "sessions" / "alpha__n2-seed1__OLD.json").write_text("{}")
        (self.results / "sessions" / "alpha__n2-seed2__OLD.json").write_text("{}")
        save_session(self.results, [], session(run="R2"))
        self.assertEqual(self.files(), ["alpha__n2-seed1__R2.json", "alpha__n2-seed2__OLD.json"])

    def test_saving_does_not_open_any_unrelated_session_file(self):
        entries = save_session(self.results, [], session(run="R1"))
        for n in range(3):
            entries = save_session(self.results, entries, session(inst=f"n2-seed{n + 2}", run="R1"))
        # An unreadable and a corrupt file that are not this key: the save must not care.
        (self.results / "sessions" / "beta__n9-seed1__R9.json").write_text("{not json")
        opened = []
        real_text, real_bytes = Path.read_text, Path.read_bytes

        def spy_text(path, *a, **kw):
            opened.append(path.name)
            return real_text(path, *a, **kw)

        def spy_bytes(path, *a, **kw):
            opened.append(path.name)
            return real_bytes(path, *a, **kw)

        with mock.patch.object(Path, "read_text", spy_text), mock.patch.object(Path, "read_bytes", spy_bytes):
            entries = save_session(self.results, entries, session(run="R2"))
        self.assertEqual(opened, [])
        self.assertEqual(self.files(), ["alpha__n2-seed1__R2.json", "alpha__n2-seed2__R1.json",
                                        "alpha__n2-seed3__R1.json", "alpha__n2-seed4__R1.json",
                                        "beta__n9-seed1__R9.json"])
        self.assertEqual(len(entries), 4)


if __name__ == "__main__":
    unittest.main()
