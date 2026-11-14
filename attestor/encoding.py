"""Borsh-compatible epoch encoding and Ed25519 payload signing."""

import base64
import hashlib
import json
import os
import struct

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


KIND_TAG = {"original": 0, "quote": 1, "reply": 2}


def _u128(value):
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if type(value) is not int or value < 0 or value >= 1 << 128:
        raise ValueError("expected unsigned 128-bit integer")
    return value.to_bytes(16, "little")


def _string(value):
    if not isinstance(value, str):
        raise ValueError("expected string")
    encoded = value.encode("utf-8")
    if len(encoded) >= 1 << 32:
        raise ValueError("string too long")
    return struct.pack("<I", len(encoded)) + encoded


def _vector(values, encode_item):
    values = list(values)
    if len(values) >= 1 << 32:
        raise ValueError("vector too long")
    return struct.pack("<I", len(values)) + b"".join(encode_item(value) for value in values)


def _tag(tag):
    try:
        kind = KIND_TAG[tag["kind"]]
    except (KeyError, TypeError):
        raise ValueError("tag kind must be original, quote, or reply")
    if type(tag.get("reply_to_token")) is not bool:
        raise ValueError("reply_to_token must be boolean")
    if type(tag.get("demo")) is not bool:
        raise ValueError("tag demo label must be boolean")
    if tag.get("votes"):
        raise ValueError("validator votes must be submitted on-chain, not in the epoch")
    fields = ("views", "likes", "replies", "retweets", "quotes")
    return (
        _string(tag["fingerprint"])
        + bytes((kind,))
        + bytes((1 if tag["demo"] else 0,))
        + b"".join(_u128(tag[field]) for field in fields)
        + bytes((1 if tag["reply_to_token"] else 0,))
        + struct.pack("<I", 0)
    )


def _account(account):
    return (
        _string(account["account_id"])
        + _string(account["x_account"])
        + bytes((1 if account["demo"] else 0,))
        + _u128(account["tag_points"])
        + _u128(account["hold_points"])
        + _u128(account["twap_balance"])
        + _vector(account["tags"], _tag)
    )


def payload_borsh(payload):
    """Serialize EpochPayload in Rust struct field order for its signature."""
    day = payload.get("day")
    if type(day) is not int or day < 0 or day >= 1 << 64:
        raise ValueError("day must be an unsigned 64-bit integer")
    if type(payload.get("demo")) is not bool:
        raise ValueError("demo must be boolean")
    contract_id = payload.get("contract_id")
    network_id = payload.get("network_id")
    if not isinstance(contract_id, str) or not contract_id.endswith(".testnet"):
        raise ValueError("contract_id must be an explicit testnet account")
    if network_id != "testnet":
        raise ValueError("network_id must be testnet")
    return (
        struct.pack("<Q", day)
        + bytes((1 if payload["demo"] else 0,))
        + _string(contract_id)
        + _string(network_id)
        + _vector(payload["accounts"], _account)
    )


def public_key_from_seed(seed):
    if len(seed) != 32:
        raise ValueError("Ed25519 private seed must be exactly 32 bytes")
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    return private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def sign_payload(payload, seed):
    """Return a JSON-ready signed payload; seed is raw 32-byte private key."""
    if len(seed) != 32:
        raise ValueError("Ed25519 private seed must be exactly 32 bytes")
    digest = hashlib.sha256(payload_borsh(payload)).digest()
    signature = Ed25519PrivateKey.from_private_bytes(seed).sign(digest)
    return {"payload": payload_to_wire(payload), "signature": base64.b64encode(signature).decode("ascii")}


def sign_payload_from_environment(payload, variable="TAG_ATTESTOR_SEED_HEX"):
    raw = os.environ.get(variable)
    if raw is None:
        raise RuntimeError("set %s in the process environment" % variable)
    try:
        seed = bytes.fromhex(raw)
    except ValueError:
        raise RuntimeError("%s must contain 64 hexadecimal characters" % variable)
    if len(seed) != 32:
        raise RuntimeError("%s must contain 64 hexadecimal characters" % variable)
    return sign_payload(payload, seed)


def signed_json(payload, seed):
    return json.dumps(sign_payload(payload, seed), separators=(",", ":"), ensure_ascii=False)


def verify_payload_signature(payload, signature_b64, public_key):
    signature = base64.b64decode(signature_b64, validate=True)
    if len(public_key) != 32 or len(signature) != 64:
        return False
    digest = hashlib.sha256(payload_borsh(payload)).digest()
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, digest)
        return True
    except Exception:
        return False


def payload_to_wire(payload):
    """Convert u128 fields to JSON strings as required by near-sdk U128."""
    wire = dict(payload)
    wire["accounts"] = []
    for account in payload["accounts"]:
        item = dict(account)
        for key in ("tag_points", "hold_points", "twap_balance"):
            item[key] = str(item[key])
        item["tags"] = []
        for tag in account["tags"]:
            proof = dict(tag)
            for key in ("views", "likes", "replies", "retweets", "quotes"):
                proof[key] = str(proof[key])
            item["tags"].append(proof)
        wire["accounts"].append(item)
    return wire
