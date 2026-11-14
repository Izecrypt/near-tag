# Submission package — TAG on NEAR (NEAR Hackathon, track: memecoins)

## Video script (~2 min, record screen + voice)

1. **Cold open (15s)**: "Most memecoins are a picture and a prayer. This one
   works for you." Show the token page.
2. **The mechanic (30s)**: hold nTAG, tag it on X — one post with
   `$nTAG + @its_izecube`. Sign in with X on the site once to bind your
   wallet (OAuth — the address never goes in a post). Engagement scores
   points (show the table). Holding scores too, time-weighted, so you
   can't farm it by buying at the last second. Every raid has points;
   caps mean one good post beats fifty spam posts.
3. **The rules are the token (30s)**: show `get_params` on the explorer.
   "Every number you see was frozen at launch. There is no admin key. The
   contract can hold and distribute its treasury, but it can never mint,
   freeze, or touch the token itself."
4. **The loop (25s)**: daily pot max 10% of treasury; earn max what you
   held that day; validators confirm the tags; 5% of every claim goes back
   to the pool; a reserve pot is earmarked for market buybacks (refill is
   permissionless once a pool is verified — stated, not shown).
5. **Live demo (15s)**: run a claim on testnet, show the 95/5 split in the
   explorer, show the epoch settle tx.
6. **Close (5s)**: "The economy used to run on a server with admin keys.
   Now the rules are the token." Repo + site links:
   github.com/Izecrypt/near-tag and ntag.trenchesnetwork.xyz.

## Recording shot list (what's actually on screen)

0:00–0:15 — https://ntag.trenchesnetwork.xyz hero: headline, mascot, live
epoch chip ticking, the three trust chips.
0:15–0:45 — scroll: 3 steps, two ways to earn, the scoring menu.
0:45–1:15 — testnet.nearblocks.io/address/tagmech-izecube.testnet: show
the contract is real — Code tab, the settled epoch via get_epoch (day
20771), the settle tx F2Nm89EqZpoTZ6VLczaC1NtCweksvh17ModHy3HQUAoK,
then a couple of the 8 claim txs showing the 95/5 amounts.
1:15–1:40 — terminal: run the reserved validator claim:
`export NEAR_TESTNET_RPC=https://rpc.testnet.fastnear.com && near call tagmech-izecube.testnet claim '{}' --accountId tagvalidator1.testnet --gas 100000000000000 --networkId testnet`
then open the resulting tx hash on nearblocks — the 95% / 5% split shows
in one transaction.
1:40–2:00 — back on the site: the epoch board + live counters; close on
the repo link.

## Submission checklist

- [ ] Public repo: github.com/Izecrypt/near-tag (README complete, honesty
      section present)
- [ ] Demo video < 3 min, hosted on YouTube (public or unlisted)
- [ ] Deployed testnet contract link (explorer)
- [x] Live site URL (https://ntag.trenchesnetwork.xyz; tag.* redirects)
- [ ] Submission form: nearhackathon.com, track = memecoins
- [ ] Public demo post on X (after submission, per hackathon rules)
- [ ] Deadline: 2026-11-14 23:59 UTC

## Post-submission (owner / brand lane)

- Build-in-public thread: the TAG story (Trenches economy → trustless NEAR
  port) with receipts. Draft lives in the content queue lane.
