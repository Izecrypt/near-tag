import os
import tempfile
import unittest

from attestor.submit_votes import build_commands


class SubmitVotesTests(unittest.TestCase):
    def test_builds_independent_validator_calls_for_each_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name in ("v1.json", "v2.json"):
                path = os.path.join(folder, name)
                with open(path, "w") as handle:
                    handle.write("test-only")
                paths.append(path)
            commands = build_commands(10, ["fp1", "fp2"],
                                      [("v1.testnet", paths[0]),
                                       ("v2.testnet", paths[1])],
                                      "tagmech.testnet")
            self.assertEqual(len(commands), 4)
            self.assertTrue(all(command[3] == "submit_vote" for command in commands))
            self.assertEqual(commands[0][6], "v1.testnet")
            self.assertEqual(commands[1][6], "v2.testnet")

    def test_rejects_duplicate_validator_or_non_testnet_key_account(self):
        with tempfile.TemporaryDirectory() as folder:
            key = os.path.join(folder, "key.json")
            with open(key, "w") as handle:
                handle.write("test-only")
            with self.assertRaises(ValueError):
                build_commands(10, ["fp"], [("v.testnet", key),
                                              ("v.testnet", key)],
                               "tagmech.testnet")
            with self.assertRaises(ValueError):
                build_commands(10, ["fp"], [("v.near", key)],
                               "tagmech.testnet")


if __name__ == "__main__":
    unittest.main()
