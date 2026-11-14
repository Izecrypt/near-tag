# Build plan — TAG on NEAR

Deadline 2026-11-14 23:59 UTC. Work top to bottom. [G#] = verification gate.

## Phase 1 — contract (est. 4h)

- [x] 1.1 near-sdk contract in `contract/`; Params, storage, one-shot `new()`.
      Proof: GitHub Actions run 43586449270 compiles the WASM target.
- [x] 1.2 Scoring constants fixed in code (R2 table + caps + multiplier).
      Proof: Rust scoring tests pass in GitHub Actions run 43586449270.
- [x] 1.3 `submit_epoch`: Ed25519/domain validation, day sequencing,
      fingerprint dedup, first-write wallet↔X links, pot/cap math, entitlements.
      Proof: contract tests and WASM build, run 43586449270.
- [x] 1.4 `claim()` with 95/5 split, pre-transfer state update, failure restore.
      Proof: claim arithmetic and failed-transfer restoration contract tests,
      run 43586449270.
- [x] 1.5 Validator registration, separate approve/reject votes, quorum, cut.
      Proof: validator tests in run 43586449270; reviewer still audits invariants.
- [x] 1.6 NEP-141 TAG receiver and separate payable native-NEAR pot.
      Proof: source compiles in run 43586449270. FT mock integration is still open.
- [ ] 1.7 `refill()` with Ref testnet swap + callback; graceful skip if no
      pool.
- [x] 1.8 Views: get_params, get_entitlement, get_epoch, treasury, pots.
      Proof: public view methods compiled in run 43586449270.
- [ ] 1.9 Unit tests incl. ALL six invariants (Architecture.md §2).
      `cargo test` passes 15 tests and the WASM release target builds in GitHub
      Actions run 43586449270. Other-machine six-invariant review remains open,
      so this item is not closed.

## Phase 2 — deploy + attestor demo (est. 2.5h)

- [ ] 2.1 Create own testnet accounts (deployer, token stand-in, 8 demo
      users, 2 validators). Deploy a standard NEP-141 as the token
      stand-in (document stand-in in README).
- [ ] 2.2 Deploy mechanics contract with params (attestor key = your own
      ed25519, record it in tasks/HANDBACK.md).
      [G2: explorer link recorded]
- [ ] 2.3 Seed treasury (transfer TAG from token deployer), seed NEAR pot.
- [x] 2.4 `attestor/score.py` pure scoring module + unit tests. Proof:
      `python3 -m unittest attestor.test_score` — 4 tests passed (2026-11-14).
- [x] 2.5 `attestor/demo_seed.py`: synthetic labeled epoch (8 users, mixed
      original/reply/quote tags, deterministic data). Proof: generator test.
- [x] 2.6 `attestor/twap.py`: real balance sampling via RPC for demo users.
      Proof: RPC parsing and TWAP arithmetic tests; no live testnet sample yet.
- [x] 2.7 `attestor/submit.py` + `submit_votes.py`: explicit testnet CLI/key
      paths for epoch submission and separate validator votes. Proof: command
      tests; no live submission yet.
- [ ] 2.8 Run full demo epoch; then ≥3 `claim()` calls.
      [G3: epoch tx hash + ≥3 claim tx hashes recorded; skim visible on
      balances; refill() executed or documented skip]

## Phase 3 — site + sim (est. 2.5h)

- [ ] 3.1 `site/index.html`: dark lab-notebook style; reads all views via
      near-api-js; claim box with MyNearWallet.
- [ ] 3.2 Serve locally, verify against deployed contract.
      [G4: screenshot or local URL reading live state]
- [x] 3.3 `sim/simulate.py`: 3 scenarios × 60 days, treasury curves with/
      without skim, 10/20/30% seed, 0/25/50/100 hold-points and 500/1000/1500
      bps sweep; baseline follows owner-approved settings. Proof:
      `cd sim && python3 simulate.py`; 5 simulation tests pass locally.
- [x] 3.4 Charts to `sim/out/`, results table into README.
      [G5: README and `sim/out/parameter_sweep.csv`; illustrative only]

## Phase 4 — README, video script, handback (est. 1h)

- [ ] 4.1 README: what/why, the loop, scoring table, honesty section
      (oracle model, demo epoch label, sybil limits, validator bounds),
      sim results, deploy info.
      [G6: honesty section present — reviewer checklist item]
- [ ] 4.2 `demo/SUBMISSION.md` filled: deployed addresses, tx hashes,
      how-to-run, demo flow for the video.
- [ ] 4.3 `tasks/HANDBACK.md`: everything the reviewer needs.
- [ ] 4.4 Push to main.

## Deviations

Log in `tasks/deviations.md` as they happen. Known-possible: Ref testnet
pool missing (skip refill, document), near-cli signing friction (use
py-near or near-api-js signer), X live mode (stub is acceptable for the
demo per PRD non-goals).
