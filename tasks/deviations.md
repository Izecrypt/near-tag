# Build deviations and environment limits

No product-scope deviations have been approved.

## Accounting clarification — 2026-11-14

- The implementation and stress model reserve outstanding gross entitlements
  before calculating the next epoch's pot. The initial formula used the full
  treasury balance and could authorize cumulative claims beyond available
  tokens when users delayed claiming. The daily 10% limit is now applied to
  `accounted_treasury - outstanding_entitlements`. This preserves the 10%
  limit while making the claim promise solvent. The per-account TWAP cap
  remains per epoch/day, as specified.
- Validator votes are separate on-chain calls by registered validators,
  rather than claims embedded in the attestor-signed payload. This ensures
  the contract counts actual validator transactions and lets rejects subtract
  from approvals. Epoch signatures also bind the target contract and NEAR
  chain ID. The SDK pin was raised to 5.30.1 for `env::chain_id()`; this
  workstation cannot compile the change.

## Local build session — 2026-11-14

- The available workstation has Python 3.8.2, but no `cargo`, `rustc`,
  `near` CLI, or Docker executable. The contract cannot be compiled locally,
  deployed, or exercised from this environment as-is.
- GitHub DNS resolution failed during the attempted vault fetch. The GitHub
  connector confirms `near-tag` still has only its `master` branch; local
  work cannot be pushed with the normal Git transport while DNS is failing.
- No testnet keys were available or used. No contract deployment, funded
  account, transaction, live site, video, or hackathon submission is claimed.
- Scoring and simulation utilities are local; the simulation remains
  exploratory and does not satisfy the parameter-recommendation gate.
- GitHub Actions compiled the contract and passed 14 Rust unit tests on the
  worker branch (run 43584626007). Local cargo is unavailable, and there is
  still no wasm build or testnet deployment evidence.
- `refill()` remains a no-op pending verification of the testnet router,
  TAG/wNEAR pool, token storage requirements, and safe minimum-output policy.
  No Ref pool absence has been proven, so this is an open implementation
  blocker, not a completed skip.
- The spec caps each epoch's entitlements but does not reserve earlier
  unclaimed obligations against later epochs. This session did not change
  that settlement rule; the reviewer must resolve it before deployment.
