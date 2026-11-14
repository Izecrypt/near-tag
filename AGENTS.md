# AGENTS.md — worker contract

You are the build agent for TAG on NEAR. The spec is complete: build exactly
it, verify everything, change nothing without a decision record.

## Hard rules

1. **Spec is law.** Deviations are allowed ONLY for documented blockers
   (e.g., Ref testnet pool missing). Every deviation gets a short note in
   `tasks/deviations.md` and the README.
2. **Immutability is the product.** Do not add admin methods, upgrade paths,
   or parameter setters "for convenience". If a test would be easier with
   one, write the test differently.
3. **Honesty is scored.** The README must state the oracle model, the demo
   epoch, sybil limits, and validator collusion bounds plainly. No
   overselling, no hidden centralization.
4. **Verify before done.** Every task in `tasks/todo.md` ends with proof:
   test output, explorer link, or a transcript. "Should work" is not done.
5. **Deadline: 2026-11-14 23:59 UTC.** If a gate is at risk, prioritize the
   demo path: deployed contract + one settled demo epoch + claims + skim +
   site reading live data. Ref buyback and live-X mode are secondary.
6. **Never commit secrets.** Testnet keys are disposable; never use or
   request mainnet keys or the owner's keys. Create your own testnet
   accounts (near-cli or implicit accounts).
7. **Git discipline:** small commits, messages that state what + proof.

## Order of work

Follow `tasks/todo.md`. Do not start the site before the contract is
deployed; do not start the sim before scoring exists.

## Handback

When all gates pass: push to `main`, write `tasks/HANDBACK.md` with deploy
addresses, tx hashes of the demo epoch + claims, site URL, test output
summary, and deviations. The reviewer deploys to the final account and
handles submission.
