import unittest

from attestor.demo_seed import build_demo_epoch
from attestor.score import Tag, score_tag


class DemoSeedTests(unittest.TestCase):
    def test_seeded_fixture_is_repeatable_and_fully_labelled(self):
        payload, posts = build_demo_epoch(20_000, "@tagdemo")
        again, posts_again = build_demo_epoch(20_000, "@tagdemo")
        self.assertEqual(payload, again)
        self.assertEqual(posts, posts_again)
        self.assertTrue(payload["demo"])
        self.assertEqual(payload["contract_id"], "tagmech.testnet")
        self.assertEqual(payload["network_id"], "testnet")
        self.assertEqual(len(payload["accounts"]), 10)
        self.assertEqual(len(posts["posts"]), 24)
        self.assertTrue(all(row["demo"] for row in posts["posts"]))
        self.assertTrue(all(account["demo"] for account in payload["accounts"]))
        self.assertTrue(all(tag["demo"] for row in payload["accounts"] for tag in row["tags"]))
        self.assertTrue(all(not tag["votes"] for row in payload["accounts"]
                            for tag in row["tags"]))

    def test_contract_tag_points_match_the_generated_proofs(self):
        payload, _ = build_demo_epoch(20_000, "@tagdemo")
        for account in payload["accounts"]:
            calculated = sum(score_tag(Tag(
                kind=tag["kind"],
                views=tag["views"],
                likes=tag["likes"],
                replies=tag["replies"],
                retweets=tag["retweets"],
                quotes=tag["quotes"],
                reply_to_token=tag["reply_to_token"],
            )) for tag in account["tags"])
            self.assertEqual(calculated, account["tag_points"])


if __name__ == "__main__":
    unittest.main()
