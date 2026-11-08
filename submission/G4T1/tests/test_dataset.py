import unittest
from pathlib import Path

DATASET = Path(__file__).resolve().parent.parent / "data" / "MY.txt"


class DatasetTest(unittest.TestCase):
    def test_dataset_has_71709_records(self):
        with DATASET.open(encoding="utf-8") as f:
            self.assertEqual(sum(1 for _ in f), 71709)


if __name__ == "__main__":
    unittest.main()
