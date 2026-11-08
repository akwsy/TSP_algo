"""Default travel period: 06:00 departure until midnight."""
import unittest

from harness.config import ConfigError, InstanceConfig


class DefaultConfigTest(unittest.TestCase):
    def test_default_period_runs_from_06_00_to_midnight(self):
        c = InstanceConfig(seed=1)
        self.assertEqual((c.departure_minute, c.period_minutes, c.deadline_minute), (360, 1080, 1440))
        self.assertEqual(c.instance_id, "n10-seed1")

    def test_old_480_period_is_now_a_named_variant(self):
        self.assertEqual(InstanceConfig(seed=1, period_minutes=480).instance_id, "n10-seed1-per480")

    def test_radius_defaults_to_150_km_and_names_the_id_only_when_different(self):
        self.assertEqual(InstanceConfig(seed=1).radius_km, 150)
        self.assertEqual(InstanceConfig(seed=1, radius_km=150.0).instance_id, "n10-seed1")
        self.assertEqual(InstanceConfig(seed=1, radius_km=50).instance_id, "n10-seed1-rad50")
        self.assertEqual(InstanceConfig(seed=1, speed_kmh=30, radius_km=25.5).instance_id,
                         "n10-seed1-spd30-rad25.5")

    def test_radius_must_be_positive(self):
        for bad in (0, -5):
            with self.assertRaises(ConfigError):
                InstanceConfig(seed=1, radius_km=bad)


if __name__ == "__main__":
    unittest.main()
