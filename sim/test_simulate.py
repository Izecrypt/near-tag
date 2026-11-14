import unittest

from sim.simulate import (DAYS, START_TREASURY, allocate_daily_payouts, run)


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

    def test_larger_starting_seed_retains_more_tokens_for_same_scenario(self):
        smaller = run(150, 1, True, start_treasury=100_000)[0][-1]
        larger = run(150, 1, True, start_treasury=200_000)[0][-1]
        self.assertGreater(larger, smaller)

    def test_hold_rate_changes_shares_and_validator_cut_needs_confirmed_tags(self):
        args = (10_000, [100], [1_000], [5_000, 5_000])
        no_holding = allocate_daily_payouts(*args, confirmed_tags=1, hold_rate=0)
        with_holding = allocate_daily_payouts(*args, confirmed_tags=1, hold_rate=100)
        no_confirmations = allocate_daily_payouts(*args, confirmed_tags=0, hold_rate=0)
        self.assertNotEqual(no_holding, with_holding)
        self.assertLess(sum(no_confirmations), sum(no_holding))
        self.assertLessEqual(sum(with_holding), 10_000)


if __name__ == "__main__":
    unittest.main()
