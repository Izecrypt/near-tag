import json
import os
import tempfile
import unittest

from attestor.submit import build_command, build_vote_command


class SubmitTests(unittest.TestCase):
    def test_command_requires_explicit_testnet_key_path(self):
        with tempfile.TemporaryDirectory() as folder:
            epoch = os.path.join(folder, "epoch.json")
            key = os.path.join(folder, "key.json")
            with open(epoch, "w") as handle:
                json.dump({"payload": {"day": 1, "demo": True,
                                        "contract_id": "tagmech.testnet",
                                        "network_id": "testnet", "accounts": []},
                           "signature": "AA=="}, handle)
            with open(key, "w") as handle:
                handle.write("test-only")
            command = build_command(epoch, "tagmech.testnet", "worker.testnet", key)
            self.assertIn("--keyPath", command)
            self.assertIn(key, command)
            self.assertIn("--networkId=testnet", command)

    def test_refuses_non_testnet_account_and_missing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            epoch = os.path.join(folder, "epoch.json")
            with open(epoch, "w") as handle:
                json.dump({"payload": {"contract_id": "tagmech.testnet",
                                        "network_id": "testnet"},
                           "signature": "AA=="}, handle)
            with self.assertRaises(ValueError):
                build_command(epoch, "tagmech.near", "worker.testnet", "/missing")

    def test_validator_vote_uses_its_own_explicit_testnet_key(self):
        with tempfile.TemporaryDirectory() as folder:
            key = os.path.join(folder, "validator.json")
            with open(key, "w") as handle:
                handle.write("test-only")
            command = build_vote_command(20_000, "fingerprint", True,
                                        "tagmech.testnet", "validator.testnet", key)
            self.assertEqual(command[3], "submit_vote")
            self.assertIn('"approve":true', command[4])
            self.assertIn(key, command)


if __name__ == "__main__":
    unittest.main()
