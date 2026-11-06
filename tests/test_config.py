"""Default travel period: 06:00 departure until midnight."""
import unittest

from harness.config import InstanceConfig


class DefaultConfigTest(unittest.TestCase):
    def test_default_period_runs_from_06_00_to_midnight(self):
        c = InstanceConfig(seed=1)
        self.assertEqual((c.departure_minute, c.period_minutes, c.deadline_minute), (360, 1080, 1440))
        self.assertEqual(c.instance_id, "n10-seed1")

    def test_old_480_period_is_now_a_named_variant(self):
        self.assertEqual(InstanceConfig(seed=1, period_minutes=480).instance_id, "n10-seed1-per480")


if __name__ == "__main__":
    unittest.main()
