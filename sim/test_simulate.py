import unittest

from sim.simulate import DAYS, START_TREASURY, run


class SimulationTests(unittest.TestCase):
    def test_run_is_deterministic_and_tracks_claim_delay(self):
        delayed = run(20, 3, True)
        self.assertEqual(delayed, run(20, 3, True))
        self.assertEqual(len(delayed[0]), DAYS + 1)
        self.assertLessEqual(delayed[0][-1], START_TREASURY)
        self.assertGreaterEqual(delayed[1], 0)
        self.assertGreaterEqual(delayed[2], 0)

    def test_claim_skim_preserves_more_balance_under_same_inputs(self):
        with_skim = run(150, 1, True)[0][-1]
        without_skim = run(150, 1, False)[0][-1]
        self.assertGreater(with_skim, without_skim)

    def test_lower_daily_pot_preserves_more_treasury(self):
        conservative = run(150, 1, True, pot_bps=500)[0][-1]
        baseline = run(150, 1, True, pot_bps=1000)[0][-1]
        self.assertGreater(conservative, baseline)


if __name__ == "__main__":
    unittest.main()
