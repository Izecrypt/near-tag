import unittest

from attestor.twap import compute_twap


class TwapTests(unittest.TestCase):
    def test_piecewise_constant_time_weighted_average(self):
        samples = [
            {"timestamp_ns": 0, "balance": 10},
            {"timestamp_ns": 5, "balance": 20},
            {"timestamp_ns": 10, "balance": 30},
        ]
        self.assertEqual(compute_twap(samples, 0, 10), 15)

    def test_uses_latest_observation_at_interval_start(self):
        samples = [
            {"timestamp_ns": 0, "balance": 10},
            {"timestamp_ns": 5, "balance": 20},
            {"timestamp_ns": 10, "balance": 30},
        ]
        self.assertEqual(compute_twap(samples, 5, 10), 20)

    def test_rejects_interval_without_starting_sample(self):
        with self.assertRaises(ValueError):
            compute_twap([{"timestamp_ns": 5, "balance": 10}], 0, 10)


if __name__ == "__main__":
    unittest.main()
