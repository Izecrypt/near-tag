import unittest

from attestor.score import Tag, score_day, score_tag


class ScoreTests(unittest.TestCase):
    def test_fixed_weights_and_multipliers(self):
        self.assertEqual(score_tag(Tag("reply", views=1, likes=1, replies=1,
                                       retweets=1, quotes=1)), 651)
        self.assertEqual(score_tag(Tag("original", views=2, likes=1)), 1300)
        self.assertEqual(score_tag(Tag("reply", replies=1, reply_to_token=True)), 150)
        self.assertEqual(score_tag(Tag("quote", quotes=1, reply_to_token=True)), 450)

    def test_token_handle_multiplier_is_only_for_quotes_and_replies(self):
        with self.assertRaises(ValueError):
            score_tag(Tag("original", views=1, reply_to_token=True))

    def test_daily_caps_are_applied_in_input_order(self):
        tags = [Tag("original", views=1) for _ in range(6)]
        tags += [Tag("quote", views=1) for _ in range(11)]
        tags += [Tag("reply", views=1) for _ in range(16)]
        scores, total = score_day(tags)
        self.assertEqual(sum(value > 0 for value in scores[:6]), 5)
        self.assertEqual(sum(value > 0 for value in scores[6:17]), 10)
        self.assertEqual(sum(value > 0 for value in scores[17:]), 15)
        self.assertEqual(total, 150)

    def test_rejects_invalid_engagement(self):
        with self.assertRaises(ValueError):
            score_tag(Tag("reply", likes=-1))
        with self.assertRaises(ValueError):
            score_tag(Tag("spam"))


if __name__ == "__main__":
    unittest.main()
