"""Build one deterministic synthetic epoch; requires an external signing key."""
import argparse
import hashlib
import json
import os
import random
import sys
import time

from attestor.encoding import public_key_from_seed, sign_payload_from_environment
from attestor.score import Tag, score_tag

DEFAULT_USERS = ["taguser%d.testnet" % n for n in range(1, 9)]
DEFAULT_VALIDATORS = ["tagvalidator%d.testnet" % n for n in range(1, 3)]


def _fingerprint(text, author_id):
    normalized = " ".join(text.lower().split())
    return hashlib.sha1((normalized + "|" + author_id).encode("utf-8")).hexdigest()


def build_demo_epoch(day, token_x_account, contract_id="tagmech.testnet",
                     users=None, validators=None,
                     decimals=24, rng_seed=20261114):
    users = list(users or DEFAULT_USERS)
    validators = sorted(validators or DEFAULT_VALIDATORS)
    if len(users) != 8 or len(validators) != 2:
        raise ValueError("demo fixture requires exactly 8 users and 2 validators")
    if len(set(users + validators)) != len(users) + len(validators):
        raise ValueError("demo user and validator accounts must be unique")
    if not 0 <= decimals <= 38:
        raise ValueError("token decimals outside supported range")

    rng = random.Random(rng_seed)
    scale = 10 ** decimals
    account_rows = []
    post_rows = []
    for index, account_id in enumerate(sorted(users), 1):
        x_account = "@tagdemo%d" % index
        kinds = ("original", "quote", "reply")
        tags = []
        tag_total = 0
        for tag_index, kind in enumerate(kinds, 1):
            wallet = account_id
            text = "%s %s %s %s demo %s post %d" % (
                "$TAG", token_x_account, wallet, x_account, kind, tag_index)
            counts = {
                "views": rng.randint(25, 240),
                "likes": rng.randint(1, 22),
                "replies": rng.randint(0, 12),
                "retweets": rng.randint(0, 9),
                "quotes": rng.randint(0, 5),
            }
            reply_to_token = kind in ("quote", "reply")
            points = score_tag(Tag(kind=kind, reply_to_token=reply_to_token, **counts))
            tag_total += points
            tags.append({
                "fingerprint": _fingerprint(text, account_id),
                "kind": kind,
                "demo": True,
                **counts,
                "reply_to_token": reply_to_token,
                # Quorum votes are submitted independently by validator accounts.
                "votes": [],
            })
            post_rows.append({
                "demo": True,
                "author_wallet": account_id,
                "author_x_account": x_account,
                "text": text,
                **counts,
                "fingerprint": tags[-1]["fingerprint"],
                "tag_points": points,
            })
        whole_tokens = rng.randint(2_000, 12_000)
        twap_balance = whole_tokens * scale
        hold_points = whole_tokens * 50 // 100
        account_rows.append({
            "account_id": account_id,
            "x_account": x_account,
            "demo": True,
            "tag_points": tag_total,
            "hold_points": hold_points,
            "twap_balance": twap_balance,
            "tags": tags,
        })

    # Validators receive their confirmed-tag counts, so they must also appear
    # as account rows with a real TWAP. They are held, but do not need X links.
    for account_id in validators:
        whole_tokens = rng.randint(5_000, 15_000)
        account_rows.append({
            "account_id": account_id,
            "x_account": "",
            "demo": True,
            "tag_points": 0,
            "hold_points": whole_tokens * 50 // 100,
            "twap_balance": whole_tokens * scale,
            "tags": [],
        })

    payload = {"day": int(day), "demo": True, "contract_id": contract_id,
               "network_id": "testnet", "accounts": account_rows}
    return payload, {"demo": True, "posts": post_rows, "rng_seed": rng_seed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=int, default=int(time.time() // 86_400))
    parser.add_argument("--token-x-account", required=True)
    parser.add_argument("--contract", default=os.environ.get("TAG_CONTRACT_ID"),
                        required=os.environ.get("TAG_CONTRACT_ID") is None)
    parser.add_argument("--out", default="out/epoch.json")
    parser.add_argument("--posts-out", default="out/demo_posts.json")
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args(argv)

    payload, posts = build_demo_epoch(args.day, args.token_x_account,
                                      contract_id=args.contract, rng_seed=args.seed)
    signed = sign_payload_from_environment(payload)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.posts_out) or ".", exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(signed, handle, indent=2, sort_keys=True)
    with open(args.posts_out, "w") as handle:
        json.dump(posts, handle, indent=2, sort_keys=True)

    public_key = public_key_from_seed(bytes.fromhex(os.environ["TAG_ATTESTOR_SEED_HEX"]))
    print("epoch=%s accounts=%d demo_posts=%d public_key=%s" % (
        args.day, len(payload["accounts"]), len(posts), public_key.hex()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
