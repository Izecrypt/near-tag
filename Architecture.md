# Architecture — TAG on NEAR

Four components: the token (meme.cooking, external), the mechanics contract
(Rust), the attestor (Python, the oracle), the site (static JS). Plus the
simulation (Python, offline).

## System diagram

```
X (posts) ---------------+        NEAR blockchain
                         |         ┌──────────────────────────────┐
                         v         │  mechanics contract (Rust)   │
                   attestor (py)   │  - params (immutable)        │
                   scores tags     │  - epoch settlement          │
                   TWAP snapshots  │  - entitlements (pull)       │
                   validator sigs  │  - claim() with 5% skim      │
                   submits epoch ->│  - refill() NEAR->TAG swap   │
                         |         └──────┬───────────────┬───────┘
                         |                | ft_transfer   | swap
                         |                v               v
                         |         holders (claims)   Ref Finance
                         |                                   |
                   validators (confirm tags)                 v
                         |                            treasury TAG
                   static site (reads contract + indexer)
```

## 1. Token (external)

- Launched via meme.cooking fair auction (testnet for the demo). Factory
  NEP-141; we do not control or modify it.
- Contract addresses needed by the mechanics contract: `token_id` (the NEP-141).
- For the demo, a plain testnet NEP-141 (near-sdk FT example) is acceptable
  as the stand-in "meme.cooking token"; document this in the README. If time
  allows, launch the real thing on meme.cooking testnet.
- Ref Finance testnet: pool token/NEAR for the buyback. If no pool exists,
  `refill()` documents this and skips (README honesty).

## 2. Mechanics contract (Rust, near-sdk 5.x) — `contract/`

Account: `tagmech.<deployer>.testnet` (worker-created; final named deploy by
reviewer). The contract's own TAG balance IS the treasury.

### Parameters (set in `new()`, immutable, publicly readable)

```rust
pub struct Params {
    pub token_id: AccountId,              // NEP-141 token
    pub daily_pot_bps: u16,               // 1000 = 10% of treasury max/day
    pub skim_bps: u16,                    // 500 = 5% of every claim
    pub validator_cut_bps: u16,           // 1000 = 10% of pot
    pub validator_threshold: U128,        // min balance to be a validator (5_000 tokens)
    pub validator_confirmations: u8,      // net confirmations a tag needs (2)
    pub hold_pts_per_token_day: u16,      // 50 = 0.5 pts per whole token/day (2dp fixed)
    pub cap_originals: u8,                // 5
    pub cap_quotes: u8,                   // 10
    pub cap_replies: u8,                  // 15
    pub multiplier_reply_to_token_bps: u16, // 150 = 1.5x
    pub attestor_pk: PublicKey,           // ed25519 key that signs epochs
    pub treasury_seed: U128,              // informational: seeded amount
}
```

Weight table (views/likes/replies/RTs/quotes) is FIXED in code per PRD R2 —
it is the spec, not a parameter.

### Storage

- `params: Params`
- `current_day: u64` (unix day of last settled epoch; epochs sequential)
- `entitlements: UnorderedMap<AccountId, u128>` (accumulated unclaimed TAG)
- `epoch_log: Vector<EpochSummary>` (day, pot, validator_cut, total_points,
  treasury_after) — bounded, keep last 90
- `validators: UnorderedSet<AccountId>` (registered, balance-checked at
  registration)
- `validator_votes` keyed by day/fingerprint, plus an indexed key list capped
  at 60,000 fingerprints/day for cleanup after settlement
- `linked_x: LookupMap<AccountId, String>` (wallet -> x account, first
  attestation wins)
- `skim_pot: u128` internal accounting is just balance deltas; track
  `near_pot: u128` (yoctoNEAR) for buybacks
- `tag_registry: UnorderedSet<String>` (canonical fingerprints already paid,
  cross-epoch dedup)

### Methods

```rust
#[init] new(params: Params)            // one-shot; no admin post-init
view get_params() -> Params
view get_entitlement(account) -> U128
view get_epoch(day) -> Option<EpochSummary>
view treasury() -> U128                // internal ledger from ft_transfer_call deposits
view pots() -> (skim_pot: U128, near_pot: U128)

register_validator()                   // asserts ft_balance_of(caller) >= threshold
submit_vote(day, fingerprint, approve) // registered caller; one vote/tag/day
submit_epoch(epoch: SignedEpochPayload)
   // verifies attestor ed25519 signature over payload hash
   // - require payload contract_id == current account and network_id == env::chain_id()
   // payload: day, demo, contract_id, network_id,
   //   Vec<AccountScore { account, x_account, tag_points,
   //   hold_points, twap_balance, tags: Vec<TagProof { fingerprint,
   //   engagement counts }> }>; votes are separate on-chain calls
   // - day must be current_day+1
   // - tag dedup: reject any fingerprint in tag_registry; insert after settle
   // - link wallet->x on first appearance
   // - validator math reads on-chain votes; net confirmations = confirms - rejects,
   //   must be >= validator_confirmations, else tag excluded
   // - pot = min(daily_pot_bps * unreserved treasury / 10000, unreserved treasury)
   // - validator_cut = validator_cut_bps * pot / 10000
   // - remaining split pro-rata by points among accounts whose payout
   //   (share + validator cut share) <= twap_balance; excess stays
   // - validator_cut split pro-rata by confirmed-tag counts among validators
   // - remove all recorded vote rows for the settled day
   // - add all amounts to entitlements; emit EpochSettled event
claim()
   // amount = entitlements[caller]; assert > 0
   // user_amount = amount * (10_000 - skim_bps) / 10_000
   // skim = amount - user_amount  (stays in contract = treasury)
   // ft_transfer(token, caller, user_amount); clear entitlement; emit Claim
refill()
   // permissionless; if near_pot >= MIN_SWAP (0.5 NEAR):
   //   swap near_pot NEAR -> TAG on Ref Finance (testnet router),
   //   near_pot = 0; received TAG is treasury (no-op accounting)
   //   cross-contract call with callback; failure leaves near_pot intact
deposit_near()                         // payable native NEAR buyback-pot deposit
ft_on_transfer()                       // accept TAG only; return unrelated tokens
```

### Invariants (tests must prove)

1. No method mutates `params`. Ever.
2. `treasury` can only decrease via `claim` (and by exactly the user
   portion) or `refill`-swap failures; skim stays.
3. An epoch's total entitlement ≤ pot ≤ 10% of unreserved treasury at settle
   time, where unreserved treasury = accounted treasury minus all outstanding
   gross entitlements.
4. No account's epoch payout exceeds its `twap_balance`.
5. A fingerprint can only be paid once, ever.
6. `claim` can only transfer what is entitled; reentrancy-safe via
   entitlement clearing before ft_transfer.

## 3. Attestor (Python 3.11, stdlib + `requests`) — `attestor/`

Two modes:

- `demo` (default, required for the hackathon demo): generates ONE labeled
  synthetic epoch: N demo wallets (created on testnet), synthetic X posts in
  real format ($nTAG + @tokenaccount — never a wallet address), engagement
  numbers drawn from a seeded RNG, TWAP from real balance sampling,
  validators = 2 demo accounts that sign confirmations. Every synthetic
  element is flagged `"demo": true` in the payload and the README says so
  plainly.
- `live` (production path, stubbed): X recent-search ingestion → engagement
  fetch → fingerprint (canonical: sha1(normalized text) + author id) →
  poster's wallet resolved via the OAuth-verified binding
  (`bindings.py` reads the tag-auth profile DB; posts never contain wallet
  addresses) → scoring per R2 → caps → validator web UI/API for
  confirmations → epoch build + ed25519 sign + submit. Ship the scoring
  module fully implemented and unit-tested; the X fetcher may be a thin
  adapter.

Components: `score.py` (pure functions: tag scoring, caps, multiplier),
`twap.py` (balance sampler via near RPC), `validate.py` (confirmation
collection + signature verification helpers), `build_epoch.py`, `submit.py`
(near signer via `near-cli` or py-near — prefer near-cli subprocess for the
demo), `demo_seed.py` (synthetic generator).

## 4. Site (static, no build step) — `site/`

Single `index.html`, dark, monospace accents (match izecube.trenchesnetwork.xyz
lab-notebook style). Reads contract views via near-api-js RPC. Sections:
params table, treasury + pots, epoch log, top taggers (from epoch log +
entitlements events), claim box (MyNearWallet connect → claim()). Deploy to
Trenches server at `ntag.trenchesnetwork.xyz` (reviewer handles DNS+nginx).

## 5. Simulation (Python, matplotlib optional) — `sim/`

Model 60 days under 3 scenarios: quiet (20 taggers/day), expected (150),
raid-season (800). Variables: tag points/day distribution, holder TWAP
distribution, claim latency. Outputs: treasury balance over time with and
without the skim; days-to-depletion table; recommended `hold_pts_per_token_day`
and seed size. Save charts to `sim/out/` and paste the results table into
README.

## 6. Security & honesty notes (README section)

- Oracle trust: the attestor is a single signed key (params.attestor_pk).
  Documented, rotate = impossible without redeploy (parameters are
  immutable) — this is a stated v1 limit with the validator layer as the
  check on it. The contract still enforces caps, dedup, TWAP ceilings, and
  pot limits even if the attestor lies about points; the validator layer
  constrains fabricated tags.
- Validator collusion: bounded by the 10% cut and confirmation counts;
  reward-only (no slashing) in v1; stated plainly.
- The mechanics contract never holds powers over the token itself.
