# Deployment and demo record — TAG on NEAR testnet (reviewer)

Date: 2026-11-14. Deployed and demonstrated by the reviewer (owner-side machine)
after worker handoff. All accounts and keys are disposable testnet-only.

## Deployment

- Mechanics contract: `tagmech-izecube.testnet`
  (https://testnet.nearblocks.io/address/tagmech-izecube.testnet)
- Deploy wasm: CI build of commit `38feedc9` (PR #1 merged to master),
  sha256 `2a1db4afac3d7eb5172c6001e5356829bbb846bbefadb50d08c75c00c34c5c07`,
  on-chain code hash verified to match.
- Reward token for the demo: `wrap.testnet` (wNEAR) as a stand-in for TAG;
  the mechanics contract never depends on token identity.
- Params at init: token wrap.testnet, pot 1000 bps (10%), skim 500 bps (5%),
  validator cut 1000 bps (10%), threshold 0.01 wNEAR, 2 net confirmations,
  50 hold points per token-day, caps 5/10/15, reply-to-token x1.5,
  attestor key 85fe6b70…e483, treasury seed 1,000,000 (informational).
- Demo site: https://tag.trenchesnetwork.xyz (reads live contract views).

## Accounts (disposable testnet)

- Funder/attestor caller: `izecube-tag.testnet`
- Validators: `tagvalidator1.testnet`, `tagvalidator2.testnet` (0.1 wNEAR each,
  registered on-chain, `register_validator`)
- Users: `taguser1.testnet` … `taguser8.testnet` (storage-registered on the
  token, synthetic X links `@tagdemo1`…`@tagdemo8`)

## Demo epoch (labeled synthetic, attestor `demo` mode)

- Day 20771, signed by attestor seed (disposable), 8 users x 3 tags
  (original, quote, reply) + 2 validator hold rows. Generator:
  `attestor/demo_seed.py --seed 20261114`.
- Treasury seeding: 4 wNEAR via `ft_transfer_call`
  (tx `8PVVAEYXERSDprjnFyUpTL7HkxUYcgqwpZdYbjVZELhf`).
- Validator votes: 48 approve votes (2 per fingerprint, on-chain
  `submit_vote`).
- Epoch settlement tx: `F2Nm89EqZpoTZ6VLczaC1NtCweksvh17ModHy3HQUAoK`
  - pot 0.4 wNEAR (exactly 10% of treasury), validator cut 0.04,
    total points 791,848, total entitlement 0.4 wNEAR (rounding dust 5 yocto).
- Claims (all SUCCESS, 95/5 split verified to the yocto):
  - taguser1 `7RcKLpzyJVRVkqvh87hTeWEkQsD8r5qgQng3RN9MyM8e`
  - taguser2 `4iFFQUQKqyx9awGUeBvG11obR9umq28eh9Pu7Yvj4WTq`
  - taguser3 `GKetrsxwZ9udzCW68rThqC9yqBVpSBtuf2P43KGa13KB`
  - taguser4 `5YZYmZwfS3Fb7jh1uC4SP38a1dR275kxTy5waEVDVSbF`
  - taguser5 `ucEasLYuhCxQSvKYsPACEETBBn8qMhV96NBFLEjNXxW`
  - taguser6 `Ff6urTmNjYaQdfffm6t9P7pCSQgoiyBBCknKCJp6zWDS`
  - taguser7 `3QNoGoHRDaLNajjdSpnYqbzuAfVfZieT2v4xNxLRm8e9`
  - taguser8 `4SUtsdceQ7QJaRVXR6DNcGeyBeotRNexbvkM7T1i5igz`
- Post-claim contract state: treasury 3.6627 wNEAR, skim pot 0.01775 wNEAR
  (5% of claimed gross, visible via `pots()`), NEAR buyback pot 0.001 NEAR.
  Validator entitlements (~0.045 wNEAR) remain unclaimed by design (reserve
  demo of outstanding-liability accounting).
- Example claim check: taguser1 entitlement 49,288.55… yocto-wNEAR,
  received balance 46,824.12… = exactly 95%; skim 5% in the pot.

## Fixes applied by reviewer during deployment (all in git history)

1. `ft_on_transfer` deposit bound + `#[payable]` + NEP-141 wire-key param
   names (`sender_id`, `amount`, `msg`). Root cause of the treasury-seed
   failure; see `tasks/deviations.md`.
2. On-chain panic messages render bare on this toolchain ("unreachable"
   without text); documented, debugging-only impact.

## Open (unchanged from worker handoff)

- `refill()` remains a no-op pending verified Ref testnet pool/router.
- Cross-contract FT mock integration test not written (unit coverage +
  live testnet evidence above stands in for the deadline).
