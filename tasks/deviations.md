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
- `refill()` remains a no-op until a compatible TAG/wNEAR testnet pool, token
  storage requirements, and a safe minimum-output policy are verified. Ref's
  official docs list `ref-finance.testnet` as the exchange and describe swaps
  as requiring a `pool_id`, input/output token IDs, and `min_amount_out`; they
  do not establish that a pool for the demo token exists. The public
  `rpc.testnet.near.org` probe from this workstation failed DNS resolution, so
  live pool state could not be checked. This is an open blocker, not evidence
  that a pool is unavailable.
  Sources: [Ref Finance deployments](https://github.com/ref-finance/docs/blob/main/README.md),
  [Ref Exchange swap interface](https://github.com/ref-finance/docs/blob/main/contracts/ref-exchange.md).

## Environment and verification — 2026-11-14

- This workstation has Python 3.8.2 but no `cargo`, `rustc`, `near` CLI, or
  Docker executable. Contract compilation therefore runs in GitHub Actions.
- Git transport DNS resolution failed in this environment. Worker changes
  were published through the GitHub connector to `worker/near-tag-build` and
  are available for review in draft PR #1. The default `master` branch was not
  changed.
- GitHub Actions run [43587463639](https://github.com/Izecrypt/near-tag/actions/runs/43587463639)
  passed Python, Rust, and the `wasm32-unknown-unknown` release build on
  commit `0127f00f37b8a7932eb4bfae1de872c450c14c99`. `cargo test` passed 19
  Rust tests and the Python suite passed 22 tests (17 attestor, 5 simulation).
  The run uploaded the WASM artifact; this status update follows it.
- No testnet keys were available or used. No contract deployment, funded
  account, transaction, live site, video, or hackathon submission is claimed.
- The simulation is exploratory and does not satisfy the parameter
  recommendation gate. No final parameter choice is inferred from it.
- The other machine owns the six-invariant review. Claim failure restoration
  and wrong contract/network replay rejection have unit coverage; there is no
  FT mock integration test.
