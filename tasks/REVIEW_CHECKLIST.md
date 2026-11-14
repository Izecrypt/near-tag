# Reviewer checklist — TAG on NEAR

Use this after the worker hands back a commit and proof artifacts. A green
test command is not proof unless the assertions cover these properties.

## Six contract invariants

1. **Parameters never change.** Compare `get_params()` before and after
   every state-changing method, callbacks, failed calls, and repeated calls.
   Confirm source exposes no owner/admin setter or upgrade method.
2. **Treasury accounting is exact.** With a mock NEP-141, a successful claim
   reduces TAG balance by exactly the 95% user transfer; the 5% remains.
   Test failed transfer/callback behavior. Verify `refill()` only changes
   treasury by the received TAG and does not silently spend or lose NEAR.
3. **Each epoch stays within its pot.** Pot is at most 10% of unreserved
   treasury (accounted treasury less all outstanding gross claims). Exercise
   zero points, zero valid
   validators, one validator, many accounts, tiny pots, integer rounding,
   and account caps. Sum *all* newly granted entitlements and prove the sum
   is <= the epoch pot, which is <= 10% of settlement-time unreserved treasury.
4. **Per-account cap includes every reward stream.** For each account,
   combine point-share and validator-share entitlements, then prove the
   epoch addition is <= its TWAP balance. Include an account that is also a
   validator and rounding-heavy distributions.
5. **Fingerprints are one-time across epochs.** Submit a fingerprint, then
   attempt it again in the same payload and a later epoch. Confirm a rejected
   epoch does not poison the registry and that two simultaneous/duplicate
   submissions cannot both pay it.
6. **Claims are entitlement-bound and reentrancy-safe.** Zero claim and
   repeat claim fail; a user cannot select an amount or recipient. Verify
   entitlement is cleared before the external transfer, with correct
   handling if the promise fails or is re-entered.

## Cross-checks before handback acceptance

- Payload signature is bound to the exact canonical bytes, contract, network,
  and epoch; wrong key, altered bytes/domain, duplicate day, skipped day, and
  replay fail.
- Account score totals are derived from eligible, confirmed proofs; input
  cannot claim arbitrary `tag_points` inconsistent with its tags.
- Validator confirm/reject evidence comes from each registered validator's
  own on-chain call; duplicate votes fail and rejects subtract from approvals.
- Validator balance is checked asynchronously at registration only. Confirm
  the README describes that bound and evaluate whether the one-time check is
  acceptable for this demo.
- Wallet-to-X link is first-write-wins; conflicting later links fail.
- Deposit/refill interfaces distinguish native NEAR from NEP-141 `ft_on_transfer`.
  A token receiver callback cannot receive native NEAR merely by implementing
  `ft_on_transfer`.
- Multiple unclaimed epochs cannot create liabilities that make later claims
  insolvent. Compare outstanding gross entitlements with the actual token
  balance after each settlement and claim.
- Inspect the actual testnet explorer state and transaction receipts for
  deploy, settlement, at least three claims, and the 5% balance delta.
- Load the public site and confirm its RPC reads reference that deployed
  contract and current testnet data.
- Reconcile every task checkbox and README claim against the exact source,
  test output, explorer link, or live site. Preserve unresolved items as open.

## Spec questions discovered before implementation

These are review questions, not approved changes to the worker's scope:

- `TagProof` lists confirming accounts but the algorithm also requires net
  confirmations after rejects; the payload schema needs explicit reject
  votes and proof that voters are registered validators.
- The specification says an account's total epoch payout is capped at TWAP,
  but does not fully define how validator rewards interact with that cap or
  where over-cap shares go. Invariant 3 still requires all granted shares
  to remain within the pot.
- The per-epoch pot cap does not reserve prior unpaid entitlements. If a
  claimant delays, later epochs may create aggregate liabilities beyond the
  contract's token balance. Tests should expose this; any accounting change
  needs an owner decision because it changes the settlement rule.
- NEAR buyback funding must be a payable native-NEAR path or a documented
  wrapped-NEAR path; `ft_on_transfer` alone is not a native-NEAR deposit.
