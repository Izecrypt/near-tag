import os
import sqlite3
import tempfile
import unittest

from attestor.bindings import load_bindings, resolve_wallet


SCHEMA = ("CREATE TABLE profiles (x_id TEXT PRIMARY KEY, x_handle TEXT, "
          "wallet TEXT, updated REAL)")


class BindingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp.close()
        self.db_path = tmp.name
        db = sqlite3.connect(self.db_path)
        db.execute(SCHEMA)
        db.executemany(
            "INSERT INTO profiles VALUES (?,?,?,?)",
            [("1", "izecube", "izecube-tag.testnet", 1.0),
             ("2", "TagDemo", "tagdemo.near", 2.0),
             ("3", "unbound", None, 3.0),
             ("4", "empty", "", 4.0)],
        )
        db.commit()
        db.close()

    def tearDown(self):
        os.unlink(self.db_path)

    def test_resolve_bound_handle_case_insensitive(self):
        self.assertEqual(resolve_wallet(self.db_path, "@IzeCube"),
                         "izecube-tag.testnet")
        self.assertEqual(resolve_wallet(self.db_path, "tagdemo"),
                         "tagdemo.near")

    def test_unbound_and_empty_wallets_resolve_to_none(self):
        self.assertIsNone(resolve_wallet(self.db_path, "@unbound"))
        self.assertIsNone(resolve_wallet(self.db_path, "@empty"))

    def test_unknown_handle_and_empty_input_resolve_to_none(self):
        self.assertIsNone(resolve_wallet(self.db_path, "@nobody"))
        self.assertIsNone(resolve_wallet(self.db_path, "@"))

    def test_load_bindings_skips_unbound(self):
        bindings = load_bindings(self.db_path)
        self.assertEqual(bindings, {"izecube": "izecube-tag.testnet",
                                    "tagdemo": "tagdemo.near"})


if __name__ == "__main__":
    unittest.main()
