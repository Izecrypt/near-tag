"""Resolve X handles to NEAR wallets through the tag-auth OAuth profile DB.

Live-mode identity binding: a handle earns only for the wallet its owner
bound by signing in with X (OAuth 2.0 PKCE) on the TAG site. No wallet
address ever appears in posts; the binding is verified server-side at
sign-in and read here when the attestor builds an epoch.

The DB schema is owned by demo/site/tag-auth.py:

    profiles (x_id TEXT PRIMARY KEY, x_handle TEXT, wallet TEXT, updated REAL)
"""
import sqlite3

SELECT_BOUND = ("SELECT x_handle, wallet FROM profiles "
                "WHERE wallet IS NOT NULL AND wallet != ''")


def load_bindings(db_path):
    """Return {x_handle_lower: wallet_lower} for every bound profile."""
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute(SELECT_BOUND).fetchall()
    finally:
        db.close()
    return {handle.lower(): wallet.lower() for handle, wallet in rows}


def resolve_wallet(db_path, x_handle):
    """Wallet bound to x_handle via OAuth, or None when unbound."""
    handle = x_handle.lstrip("@").lower()
    if not handle:
        return None
    return load_bindings(db_path).get(handle)
