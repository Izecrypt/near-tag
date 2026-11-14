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
5. The daily pot is at most **10% of the treasury**. Each account can earn
   at most its **time-weighted balance** that day. Points pay pro-rata.
6. Rewards are **claimed**, not pushed (gas-safe). Every claim takes a **5%
   skim** back to the treasury ("every reward feeds the pool").
7. A launch-funded NEAR pot pays for **market buybacks**: anyone can call
   the permissionless `refill()`, which swaps NEAR for TAG on Ref Finance
   and tops the treasury. Bought tokens are exactly what gets distributed.

## Status

Spec complete (2026-11-14). Build by worker agent per `tasks/todo.md`.
Demo target: NEAR testnet, submission before 2026-11-14 23:59 UTC.

## Docs

- `PRD.md` — what and why, requirements
- `Architecture.md` — full system design, function-level contract spec
- `Architecture-essentials.md` — condensed truths and commands
- `AGENTS.md` — build rules and verification gates (worker contract)
- `tasks/todo.md` — ordered build plan
- `demo/SUBMISSION.md` — video script and submission checklist
