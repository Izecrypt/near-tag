"""Sample token balances over RPC and compute a time-weighted average."""
import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request

RPC_URL = "https://rpc.testnet.near.org"


def rpc_call(method, params, rpc_url=RPC_URL, timeout=20):
    request = urllib.request.Request(
        rpc_url,
        data=json.dumps({"jsonrpc": "2.0", "id": "tag-twap", "method": method,
                         "params": params}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("NEAR RPC request failed: %s" % exc)
    if body.get("error"):
        raise RuntimeError("NEAR RPC error: %s" % body["error"])
    return body["result"]


def read_ft_balance(token_id, account_id, rpc_url=RPC_URL):
    args = base64.b64encode(json.dumps({"account_id": account_id},
                                       separators=(",", ":")).encode()).decode("ascii")
    result = rpc_call("query", {"request_type": "call_function", "finality": "final",
                                "account_id": token_id, "method_name": "ft_balance_of",
                                "args_base64": args}, rpc_url)
    raw = bytes(result["result"]).decode("utf-8")
    balance = json.loads(raw)
    if isinstance(balance, str) and balance.isdigit():
        balance = int(balance)
    if type(balance) is not int or balance < 0:
        raise RuntimeError("ft_balance_of returned an invalid U128")
    block = rpc_call("block", {"block_id": result["block_height"]}, rpc_url)
    timestamp_ns = int(block["header"]["timestamp_nanosec"])
    return {"timestamp_ns": timestamp_ns,
            "block_height": int(result["block_height"]), "balance": balance}


def compute_twap(samples, start_ns=None, end_ns=None):
    """Piecewise-constant TWAP over samples in chain-time nanoseconds."""
    ordered = sorted(samples, key=lambda item: item["timestamp_ns"])
    if not ordered:
        raise ValueError("at least one balance sample is required")
    start_ns = ordered[0]["timestamp_ns"] if start_ns is None else start_ns
    end_ns = ordered[-1]["timestamp_ns"] if end_ns is None else end_ns
    if end_ns <= start_ns:
        raise ValueError("TWAP interval must have positive duration")
    active = None
    for sample in ordered:
        if sample["timestamp_ns"] <= start_ns:
            active = sample
        else:
            break
    if active is None:
        raise ValueError("no sample at or before TWAP start")
    cursor = start_ns
    weighted = 0
    for sample in ordered:
        timestamp = sample["timestamp_ns"]
        if timestamp <= start_ns:
            continue
        if timestamp >= end_ns:
            break
        weighted += active["balance"] * (timestamp - cursor)
        cursor = timestamp
        active = sample
    weighted += active["balance"] * (end_ns - cursor)
    return weighted // (end_ns - start_ns)


def sample_account(token_id, account_id, duration, interval, rpc_url=RPC_URL,
                   sleep=time.sleep):
    if duration <= 0 or interval <= 0:
        raise ValueError("duration and interval must be positive")
    samples = []
    deadline = time.monotonic() + duration
    while True:
        sample = read_ft_balance(token_id, account_id, rpc_url)
        samples.append(sample)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep(min(interval, remaining))
    start_ns = samples[0]["timestamp_ns"]
    end_ns = samples[-1]["timestamp_ns"]
    if end_ns <= start_ns:
        # Local clock duration is a conservative fallback if the RPC reports
        # the same finalized block timestamp for close consecutive samples.
        end_ns = start_ns + int(duration * 1_000_000_000)
    return {"account_id": account_id, "start_ns": start_ns, "end_ns": end_ns,
            "twap_balance": compute_twap(samples, start_ns, end_ns), "samples": samples}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-id", required=True)
    parser.add_argument("--account", action="append", required=True)
    parser.add_argument("--duration", type=int, default=86_400,
                        help="sampling window in seconds (default: one day)")
    parser.add_argument("--interval", type=int, default=600)
    parser.add_argument("--rpc", default=RPC_URL)
    parser.add_argument("--out", default="out/twap.json")
    args = parser.parse_args(argv)

    records = [sample_account(args.token_id, account, args.duration, args.interval, args.rpc)
               for account in args.account]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump({"demo": True, "token_id": args.token_id, "records": records},
                  handle, indent=2)
    print("saved %d accounts to %s" % (len(records), args.out))


if __name__ == "__main__":
    main()
