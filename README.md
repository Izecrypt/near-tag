# TAG on NEAR — the tag-to-earn memecoin, made trustless

TAG is a memecoin where the meme works for its holders: tag the token on X
and earn, hold and earn more. The economy is ported from the TAG bagworking
system built on the Trenches platform (spec: `Tag Points Economy Spec`,
2026-09-20, Ize-confirmed), where it ran server-side with admin keys. Here
the same economy runs in a NEAR contract with **immutable parameters and no
admin key** — the rules are the token.

Built for the NEAR Hackathon track **Memecoins With Mechanics**
("the joke needs rules", `memecoins` track id). Judged on the mechanic, not
the chart.

## The loop

1. Token launches on **meme.cooking** (fair auction → LP on Ref Finance,
   locked). Factory-standard NEP-141: no mint, no fee inside the token, no
   admin powers over it, ever.
2. The **mechanics contract** holds a reward treasury (seeded at launch).
3. Every day, two streams earn points:
   - **Tagging**: posts on X containing the token's cashtag + X account +
     your wallet address. Scored by the Trenches engagement table, capped
     per day, verified by validators.
   - **Holding**: your time-weighted average balance across the day.
4. Validators (holders above a threshold) confirm tag proofs and take a 10%
   cut of the daily pot.
5. The daily pot is at most **10% of treasury after outstanding claims are
   reserved**. Each account can earn at most its **time-weighted balance** that
   day. Points pay pro-rata.
6. Rewards are **claimed**, not pushed (gas-safe). Every claim takes a **5%
   skim** back to the treasury ("every reward feeds the pool").
7. The design reserves a launch-funded NEAR pot for **market buybacks**. The
   current `refill()` is disabled pending testnet router and pool verification;
   no swap is claimed as implemented or executed yet.

## Status

The implementation is on the worker draft branch. GitHub Actions run 43586763317
passed 17 Rust tests, 22 Python tests (17 attestor + 5 simulation), and the
`wasm32-unknown-unknown` release build. It also uploaded the contract WASM as a
short-lived workflow artifact.
The testnet demo, live site, video, and submission are not complete. See
`tasks/todo.md` and `tasks/deviations.md` for proof and open gates. No deployed
address or transaction hash is claimed.

Demo target: NEAR testnet, submission before 2026-11-14 23:59 UTC.

## Fixed scoring rules

| Activity | Points |
|---|---:|
| View | 1 |
| Like | 50 |
| Reply | 100 |
| Retweet | 200 |
| Quote | 300 |
| Original post multiplier | ×25 |
| Quote/reply to the token account | ×1.5 |
| Hold | 0.5 per whole token per day, time-weighted |

Daily tag caps are 5 originals, 10 quotes, and 15 replies. A post is eligible
only when the attestor identifies the cashtag, token X account, and wallet
link; validator votes are separate on-chain transactions.

## Simulation status

`sim/simulate.py` is a deterministic sensitivity model, not a forecast or
production-optimal parameter recommendation. It uses a normalized 1,000,000-token
supply and the owner-approved 20% seed (200,000 tokens) for its baseline;
random per-user tag scores and balances; 0/25/50/100 hold-points-per-token-day
rates; and scenario claim delays of 3, 1, and 0 days. It applies the
contract's outstanding-gross-entitlement reserve and 95/5 claim accounting.
It assumes two validators approve every modeled accepted tag and split the
validator cut evenly. It does not model real TWAP sampling, X ingestion, Ref
swaps, or adversarial attestor behavior. Run from `sim/` with
`python3 simulate.py`; output is written to `sim/out/`.

The fixed-seed 20%-seed / 50-hold-points / 1,000-bps-pool baseline produced:

| Scenario | Modeled claim delay | Treasury after 60 days, with skim | Without skim | Unpaid gross entitlement at day 60 |
|---|---:|---:|---:|---:|
| Quiet (20 taggers/day) | 3 days | 876 / 200,000 | 616 / 200,000 | 203 |
| Expected (150 taggers/day) | 1 day | 1,333 / 200,000 | 1,164 / 200,000 | 62 |
| Raid season (800 taggers/day) | 0 days | 4,669 / 200,000 | 4,527 / 200,000 | 0 |

These outputs are highly sensitive to the simplified random balance caps and
claim-delay assumptions; they are not estimates of real treasury lifetime.
The `sim/out/parameter_sweep.csv` compares 0/25/50/100 hold points per token
day, 10%/20%/30% of supply as seed, and 500/1,000/1,500 bps daily pots. It
shows sensitivity to the inputs, not a robust optimum: scores, balances, and
claim delays are simplified and randomly seeded. Keep the spec's 50 hold
points, 20% supply seed, 1,000 bps daily pot, and 500 bps claim skim as the
demo baseline; revisit with real holder and claim data. See `sim/out/treasury.svg`
and `sim/out/results.csv`.

## Security and honesty limits

- **Oracle:** one Ed25519 attestor signs each epoch payload, bound to the
  target contract and NEAR chain ID. Rotation requires redeployment because
  parameters are immutable. The contract verifies that
  signature and enforces daily scoring caps, fingerprint deduplication,
  validator quorum, the pot limit, and the per-account TWAP ceiling; it
  cannot independently verify X engagement or the attestor's TWAP samples.
- **Demo status:** no demo epoch has been submitted. Future generated posts
  and engagement must be labeled synthetic DEMO data.
- **Sybil limits:** a wallet's first attested X-account link is permanent;
  the contract does not prove real-world identity, and separate wallets may
  still be controlled by one person. Fingerprints can only be paid once.
- **Validators:** each registered validator submits an on-chain vote;
  confirmations are reward-only, without slashing. A tag needs the configured
  net confirmation count. Validator rewards are bounded
  by the configured cut of that day's pot, but colluding validators can
  still approve fabricated evidence within that bound. The 5,000-token
  threshold is checked at registration and is not re-checked at vote time.
- **Token custody:** the mechanics contract cannot mint, burn, freeze, or
  change transfers of the external NEP-141 token. Treasury accounting is
  tracked through `ft_transfer_call` deposits and successful claims; direct
  `ft_transfer` donations cannot be observed by the mechanics contract.
- **Outstanding claims:** the implementation subtracts all unclaimed gross
  entitlements from treasury before calculating a later epoch's pot. The
  simulation applies the same gross-liability reserve before later settlements.
- **Buyback:** the current `refill()` is a documented no-op until the testnet
  router, TAG/wNEAR pool, token storage, and minimum-output behavior are
  verified. No buyback is claimed as executed.

## Docs

- `PRD.md` — what and why, requirements
- `Architecture.md` — full system design, function-level contract spec
- `Architecture-essentials.md` — condensed truths and commands
- `AGENTS.md` — build rules and verification gates (worker contract)
- `tasks/todo.md` — ordered build plan
- `demo/SUBMISSION.md` — video script and submission checklist
