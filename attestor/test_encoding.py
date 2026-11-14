import base64
import unittest

from attestor.encoding import (
    payload_borsh,
    public_key_from_seed,
    sign_payload,
    verify_payload_signature,
)


class EncodingTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "day": 7,
            "demo": True,
            "contract_id": "tagmech.testnet",
            "network_id": "testnet",
            "accounts": [{
                "account_id": "alice.testnet",
                "x_account": "@alice",
                "demo": True,
                "tag_points": 1,
                "hold_points": 2,
                "twap_balance": 3,
                "tags": [{
                    "fingerprint": "fp",
                    "kind": "reply",
                    "demo": True,
                    "views": 1,
                    "likes": 0,
                    "replies": 1,
                    "retweets": 0,
                    "quotes": 0,
                    "reply_to_token": True,
                    "votes": [],
                }],
            }],
        }
        self.seed = bytes(range(32))

    def test_borsh_bytes_are_deterministic(self):
        encoded = payload_borsh(self.payload)
        self.assertEqual(encoded[:9], b"\x07\0\0\0\0\0\0\0\x01")
        self.assertEqual(payload_borsh(self.payload), encoded)

    def test_signature_verifies_and_covers_payload(self):
        signed = sign_payload(self.payload, self.seed)
        signature = base64.b64decode(signed["signature"])
        self.assertEqual(len(signature), 64)
        self.assertTrue(verify_payload_signature(
            self.payload, signed["signature"], public_key_from_seed(self.seed)))
        changed = dict(self.payload, demo=False)
        self.assertFalse(verify_payload_signature(
            changed, signed["signature"], public_key_from_seed(self.seed)))
        changed_domain = dict(self.payload, contract_id="other.testnet")
        self.assertFalse(verify_payload_signature(
            changed_domain, signed["signature"], public_key_from_seed(self.seed)))

    def test_rejects_invalid_wire_values(self):
        with self.assertRaises(ValueError):
            payload_borsh(dict(self.payload, demo="true"))
        with self.assertRaises(ValueError):
            payload_borsh(dict(self.payload, day=-1))
        with self.assertRaises(ValueError):
            payload_borsh(dict(self.payload, network_id="mainnet"))
        populated = dict(self.payload)
        populated["accounts"] = [dict(self.payload["accounts"][0])]
        populated["accounts"][0]["tags"] = [dict(self.payload["accounts"][0]["tags"][0])]
        populated["accounts"][0]["tags"][0]["votes"] = [
            {"validator_id": "v1.testnet", "approve": True}]
        with self.assertRaises(ValueError):
            payload_borsh(populated)


if __name__ == "__main__":
    unittest.main()
