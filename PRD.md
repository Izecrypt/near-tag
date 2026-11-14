# PRD — TAG on NEAR

## Problem

Memecoins are static: a picture, a ticker, and hope. Holders have nothing to
do and no reason to do it together. The chart is the only mechanic, so the
chart is all anyone talks about.

## Product

TAG, a memecoin where the economy is the mechanic. Holders earn the token by
working for it: tagging it on X (engagement-scored, capped, validator-verified)
and holding it (time-weighted). A fixed-supply treasury pays the rewards; a
5% claim skim and launch-funded buybacks keep the pool alive; every parameter
is frozen at launch with no admin key.

The launch baseline allocates 20% of initial token supply to the rewards
treasury. This is a pre-launch supply allocation, not an admin-adjustable
parameter after deployment.

The economy is a trustless port of the TAG bagworking system designed for the
Trenches platform (points economy spec, Ize-confirmed 2026-09-20). Trenches
proved the design; TAG on NEAR removes the admin.

## Non-goals (v1)

- No trading points stream, no referral stream (deliberately cut; both exist
  in the Trenches spec and are documented as future levers).
- No slashing for validators (reward-only validation in v1).
- No automatic X ingestion dependency: the demo runs a labeled DEMO epoch
  generator; production X ingestion is the attestor's `live mode`.

## Requirements

### R1 — token
Launch via meme.cooking fair auction (testnet for demo). Token is a
factory-standard NEP-141. The mechanics contract has NO power over the token
(cannot mint, burn, freeze, or modify transfers).

### R2 — tagging stream
A tag counts only if the post contains: `$TICKER` + `@<token_x_account>` +
the holder's NEAR wallet address (post-your-wallet linking). Scoring (exact
Trenches table):

- view 1 / like 50 / reply 100 / RT 200 / quote 300
- original posts ×25; replies ×1
- per-day caps: 5 originals + 10 quotes + 15 replies (further tags that day
  score zero)
- quoting or replying directly to a post by the token's X account: ×1.5
  (the Trenches "verified handle multiplier", adapted)

### R3 — holding stream
Holding points accrue from the account's time-weighted average balance
(TWAP) across the day (attestor samples balances every ~10 minutes). Holding
rate: `hold_points = twap_balance / 10^decimals * hold_pts_per_token_day`
with `hold_pts_per_token_day` fixed at launch (start: 0.5 points per whole
token held per day; tuning via `sim/`).

### R4 — settlement
Once per day the attestor submits the epoch (signed): per-account
{tag_points, hold_points, twap_balance, linked_x_account, counted_tag_ids}.
Contract computes:
- `available = treasury - outstanding_gross_entitlements`
- `pot = min(daily_pot_bps (1000 = 10%) * available / 10_000, available)`
- `validator_cut = validator_cut_bps (1000 = 10%) * pot` split pro-rata
  among validators by confirmed tags
- remainder split pro-rata by total points
- per-account payout capped at its `twap_balance` (earn no more than you
  held, per day); this is a per-epoch/day cap
Entitlements are stored; users **claim** (pull pattern).

### R5 — the 5% and the buyback
- `claim`: 95% to the user, 5% back to treasury (recycles the pool).
- Creator-funded NEAR buyback pot in the contract; `refill()` is
  permissionless: swaps NEAR → TAG on Ref Finance (testnet), proceeds to
  treasury. Callable by anyone, no admin.

### R6 — validators
- Registration: any account holding ≥ `validator_threshold` (set at launch;
  start: 5,000 tokens) registers as validator.
- Validation: validators call `submit_vote` to confirm/reject each submitted
  tag (post exists, matches fingerprint, engagement numbers plausible). Votes
  are recorded on-chain independently of the attestor-signed epoch. A tag needs ≥
  `validator_confirmations` (start: 2) net confirmations to count.
- Validator rewards: pro-rata share of the 10% cut by tags confirmed.

### R7 — immutability
All parameters set at `new()`, publicly readable, NO admin methods. The
contract owner account holds no post-init powers.

### R8 — the page
Static site: parameters, treasury balance, buyback pots, epoch history, top
taggers, personal entitlement + claim button (MyNearWallet via near-api-js).

### R9 — honesty (README, required by the track)
Sybil/limits written plainly: wallet↔X link via posted address (one X
account per wallet, first-link wins); canonical fingerprint dedup per post;
TWAP hold requirement; daily pot cap; per-account earn cap = TWAP balance;
validator collusion bounded by the 10% cut and the confirmation count;
DEMO epoch data is labeled as such.

### R10 — simulation
`sim/` models 60 days under 3 scenarios (quiet / expected / raid-season),
outputs supply/treasury-lifetime charts and the recommended parameter table
(pot bps, seed size, skim effect). Results embedded in README.

## Success criteria (demo)

- Contract deployed on NEAR testnet, verified on explorer.
- One full demo epoch settled end-to-end: tags scored, TWAP measured,
  validators confirmed, entitlements stored, claim executed with the 5% skim,
  `refill()` buyback executed.
- Static page live showing live state from testnet.
- Simulation charts in README.
- Submitted to the NEAR hackathon (track: memecoins) before 2026-11-14
  23:59 UTC with a ≤3 min demo video.
