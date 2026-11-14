"""Submit each demo fingerprint with separate validator testnet keys."""
import argparse
import json
import os
import subprocess
import sys

from attestor.submit import build_vote_command


def build_commands(day, fingerprints, validator_keys, contract_id, near_cli="near"):
    if not validator_keys:
        raise ValueError("provide at least one explicit validator account/key pair")
    if len({account for account, _ in validator_keys}) != len(validator_keys):
        raise ValueError("validator accounts must be unique")
    commands = []
    for fingerprint in fingerprints:
        for account_id, key_path in validator_keys:
            commands.append(build_vote_command(day, fingerprint, True, contract_id,
                                               account_id, key_path, near_cli))
    return commands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--posts", default="out/demo_posts.json")
    parser.add_argument("--contract", default=os.environ.get("TAG_CONTRACT_ID"),
                        required=os.environ.get("TAG_CONTRACT_ID") is None)
    parser.add_argument("--validator-key", action="append", required=True,
                        metavar="ACCOUNT=KEY_PATH")
    parser.add_argument("--near-cli", default="near")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    validator_keys = []
    try:
        for item in args.validator_key:
            account, separator, key_path = item.partition("=")
            if not separator or not account or not key_path:
                raise ValueError("each --validator-key must be ACCOUNT=KEY_PATH")
            validator_keys.append((account, key_path))
        with open(args.posts) as handle:
            data = json.load(handle)
        if data.get("demo") is not True:
            raise ValueError("refusing to vote on unlabeled/non-demo input")
        fingerprints = [post["fingerprint"] for post in data.get("posts", [])]
        if not fingerprints or len(fingerprints) != len(set(fingerprints)):
            raise ValueError("posts must have unique fingerprints")
        commands = build_commands(args.day, fingerprints, validator_keys,
                                  args.contract, args.near_cli)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    for command in commands:
        if args.dry_run:
            print(json.dumps(command))
        else:
            subprocess.run(command, check=True, text=True)
    print("prepared %d on-chain validator votes" % len(commands))
    return 0


if __name__ == "__main__":
    sys.exit(main())
