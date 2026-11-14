# Build deviations and environment limits

No product-scope deviations have been approved. The items below record
implementation clarifications and gates that remain open.

## Accounting clarification — 2026-11-14

- Settlement reserves outstanding gross entitlements before calculating a
  later epoch's pot. Without this reserve, delayed claims could let cumulative
  promises exceed the treasury balance. The daily 10% limit is applied to
  accounted treasury less outstanding entitlements; the per-account TWAP cap
  remains per epoch/day. This clarification is implemented and has contract
  unit coverage.
- Validator votes are separate on-chain calls by registered validators. This
  makes approval and rejection counts reflect actual validator transactions.
  Epoch signatures bind both the target contract and NEAR chain ID. The SDK
  pin is 5.30.1 for `env::chain_id()`.
- `refill()` remains a no-op until the testnet router, TAG/wNEAR pool, token
  storage requirements, and safe minimum-output policy are verified. This is
  an open blocker, not evidence that a pool is unavailable.

## Environment and verification — 2026-11-14

- This workstation has Python 3.8.2 but no `cargo`, `rustc`, `near` CLI, or
  Docker executable. Contract compilation therefore runs in GitHub Actions.
- Git transport DNS resolution failed in this environment. Worker changes
  were published through the GitHub connector to `worker/near-tag-build` and
  are available for review in draft PR #1. The default `master` branch was not
  changed.
- GitHub Actions run 43585248890 passed the Python and Rust jobs on commit
  `ea4b93f9c0ce8867c1ddfaa39523c42554836115`; `cargo test` passed 15 Rust
  tests. The Python suite has 21 tests. This does not constitute a WASM build.
- No testnet keys were available or used. No contract deployment, funded
  account, transaction, live site, video, or hackathon submission is claimed.
- The simulation is exploratory and does not satisfy the parameter
  recommendation gate. No final parameter choice is inferred from it.
- The other machine owns the six-invariant review. Claim failure restoration
  and wrong contract/network replay rejection have unit coverage; there is no
  FT mock integration test.
