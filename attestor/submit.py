"""Submit one signed epoch with an explicitly selected disposable testnet key."""
import argparse
import json
import os
import subprocess
import sys


def _require_testnet_account(value, label):
    if not isinstance(value, str) or not value.endswith(".testnet"):
        raise ValueError("%s must be an explicit .testnet account" % label)


def build_command(epoch_path, contract_id, caller_id, key_path, near_cli="near"):
    _require_testnet_account(contract_id, "contract id")
    _require_testnet_account(caller_id, "caller id")
    if not key_path or not os.path.isfile(key_path):
        raise ValueError("explicit disposable testnet key file is required")
    with open(epoch_path) as handle:
        signed = json.load(handle)
    if not isinstance(signed, dict) or set(("payload", "signature")) - set(signed):
        raise ValueError("epoch file must contain payload and signature")
    if not isinstance(signed["payload"], dict):
        raise ValueError("signed epoch payload must be an object")
    if signed["payload"].get("contract_id") != contract_id or \
            signed["payload"].get("network_id") != "testnet":
        raise ValueError("signed epoch domain does not match target contract/testnet")
    args = json.dumps({"signed": signed}, separators=(",", ":"), ensure_ascii=False)
    return [near_cli, "call", contract_id, "submit_epoch", args,
            "--accountId", caller_id, "--networkId=testnet", "--depositYocto=0",
            "--gas=200000000000000", "--keyPath", key_path]


def build_vote_command(day, fingerprint, approve, contract_id, caller_id,
                       key_path, near_cli="near"):
    _require_testnet_account(contract_id, "contract id")
    _require_testnet_account(caller_id, "caller id")
    if not key_path or not os.path.isfile(key_path):
        raise ValueError("explicit disposable validator testnet key file is required")
    if type(day) is not int or day < 0:
        raise ValueError("vote day must be a non-negative integer")
    if not isinstance(fingerprint, str) or not fingerprint or len(fingerprint) > 128:
        raise ValueError("invalid fingerprint")
    args = json.dumps({"day": day, "fingerprint": fingerprint,
                       "approve": bool(approve)}, separators=(",", ":"))
    return [near_cli, "call", contract_id, "submit_vote", args,
            "--accountId", caller_id, "--networkId=testnet", "--depositYocto=0",
            "--gas=50000000000000", "--keyPath", key_path]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epoch")
    parser.add_argument("--vote-day", type=int)
    parser.add_argument("--vote-fingerprint")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--contract", default=os.environ.get("TAG_CONTRACT_ID"))
    parser.add_argument("--caller", default=os.environ.get("TAG_CALLER_ACCOUNT"))
    parser.add_argument("--key-path", default=os.environ.get("TAG_TESTNET_KEY_PATH"))
    parser.add_argument("--near-cli", default="near")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.contract or not args.caller:
        parser.error("set TAG_CONTRACT_ID and TAG_CALLER_ACCOUNT or pass both options")
    try:
        if args.vote_day is not None or args.vote_fingerprint is not None:
            if args.vote_day is None or args.vote_fingerprint is None or args.epoch:
                raise ValueError("vote mode needs --vote-day and --vote-fingerprint only")
            command = build_vote_command(args.vote_day, args.vote_fingerprint,
                                         not args.reject, args.contract, args.caller,
                                         args.key_path, args.near_cli)
        else:
            if not args.epoch:
                raise ValueError("provide --epoch or vote options")
            command = build_command(args.epoch, args.contract, args.caller,
                                    args.key_path, args.near_cli)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps(command))
        return 0
    result = subprocess.run(command, check=True, text=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
