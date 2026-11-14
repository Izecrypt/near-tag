# Architecture essentials — the truths and the commands

Read this before Architecture.md when you need a quick re-orient.

## Truths

1. The token is EXTERNAL (meme.cooking factory NEP-141). The mechanics
   contract has zero powers over it. Treasury = the mechanics contract's own
   token balance.
2. Parameters are set once in `new()` and are immutable. No admin methods
   exist. Tests must prove this.
3. Rewards are PULL: `submit_epoch` stores entitlements, users call
   `claim()`. Claim = 95% user / 5% treasury skim.
4. Daily pot ≤ 10% of treasury. Per-account earn ≤ its time-weighted balance
   for that day. Points pay pro-rata (tag points + hold points).
5. Validators confirm tags; 10% of the pot goes to validators pro-rata by
   confirmed tags. Registration requires ≥ 5,000 tokens.
6. `refill()` is permissionless: swaps the contract's NEAR pot for TAG on
   Ref testnet and tops the treasury.
7. The demo runs a LABELED synthetic epoch (attestor `demo` mode). Honesty
   about this in the README is a requirement, not an option.
8. Scoring table is FIXED in code: view 1 / like 50 / reply 100 / RT 200 /
   quote 300; originals ×25; caps 5/10/15 per day; reply-to-token-post ×1.5.

## Component map

- `contract/` — Rust near-sdk. See Architecture.md §2 for the exact method
  list and invariants.
- `attestor/` — Python. `score.py` (pure scoring, unit-tested), `twap.py`,
  `demo_seed.py`, `submit.py`. Demo mode must run end-to-end.
- `site/` — static index.html, near-api-js reads, MyNearWallet claim.
- `sim/` — 60-day treasury simulation, 3 scenarios, charts + table.
- `demo/SUBMISSION.md` — video script + submission checklist.

## Commands (worker)

```bash
# contract
cd contract && cargo near build        # or cargo build --target wasm32
# tests
cd contract && cargo test
# demo attestor (testnet)
cd attestor && python3 demo_seed.py --count 8 --validators 2
cd attestor && python3 submit.py --epoch out/epoch.json
# sim
cd sim && python3 simulate.py
```

## Verification gates (must pass before handback)

1. `cargo test` green, including the six invariants in Architecture.md §2.
2. Contract deployed to testnet; explorer link recorded.
3. One full demo epoch settled; ≥3 claims executed; skim visible; `refill()`
   executed (or documented skip if no Ref pool).
4. Site serves live data from the deployed contract.
5. Sim charts + parameter table in README.
6. README honesty section complete.
