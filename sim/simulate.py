"""A transparent, seeded 60-day treasury stress model (not a forecast)."""
import csv
import os
import random

DAYS = 60
SEED = 20261114
SUPPLY = 1_000_000
START_TREASURY = SUPPLY * 20 // 100
POT_BPS = 1000
POT_SWEEP_BPS = (500, 1000, 1500)
SEED_SWEEP = (SUPPLY * 10 // 100, SUPPLY * 20 // 100,
              SUPPLY * 30 // 100)
HOLD_RATE_SWEEP = (0, 25, 50, 100)
SKIM_BPS = 500
SCENARIOS = {"quiet": (20, 3), "expected": (150, 1), "raid-season": (800, 0)}


def allocate_daily_payouts(pot, tag_scores, balances, validator_balances,
                           confirmed_tags, hold_rate):
    """Allocate one modeled epoch using the contract's two reward streams."""
    validator_cut = pot // 10
    user_budget = pot - validator_cut
    user_points = [tag_score + balance * hold_rate // 100
                   for tag_score, balance in zip(tag_scores, balances)]
    points_by_account = user_points + [
        balance * hold_rate // 100 for balance in validator_balances]
    balances_by_account = balances + validator_balances
    total_points = sum(points_by_account)
    payouts = []
    for points, balance in zip(points_by_account, balances_by_account):
        share = user_budget * points // total_points if total_points else 0
        payouts.append(min(share, balance))
    if confirmed_tags:
        # Exactly two modeled validators meet the quorum for each accepted
        # tag, so their confirmed-tag weights are equal.
        validator_share = validator_cut // 2
        payouts.extend(min(validator_share, balance)
                       for balance in validator_balances)
    return payouts


def run(taggers, claim_delay, skim_enabled, pot_bps=POT_BPS,
        start_treasury=START_TREASURY, hold_rate=50):
    rng = random.Random(SEED + taggers)
    treasury = start_treasury
    history = [treasury]
    pending = []
    failed_claims = 0
    for _day in range(1, DAYS + 1):
        available = max(0, treasury - sum(gross for _, gross in pending))
        pot = min(available * pot_bps // 10000, available)
        balances = [rng.randint(100, 50000) for _ in range(taggers)]
        tag_scores = [rng.randint(100, 10000) for _ in range(taggers)]
        validator_balances = [rng.randint(5_000, 15_000),
                              rng.randint(5_000, 15_000)]
        # Every modeled accepted tag meets the two-validator quorum, so both
        # validators receive equal confirmed-tag counts. The validator cut is
        # paid only when at least one tag was confirmed.
        confirmed_tags = sum(rng.randint(1, 3) for _ in range(taggers))
        payouts = allocate_daily_payouts(
            pot, tag_scores, balances, validator_balances,
            confirmed_tags, hold_rate)
        paid = min(sum(payouts), pot)
        # Reserve each unpaid gross entitlement before calculating tomorrow's
        # pot. Claims transfer 95% and leave the modeled skim in treasury.
        pending.append((_day + claim_delay, paid))
        due, pending = [p for p in pending if p[0] <= _day], [p for p in pending if p[0] > _day]
        for _, gross in due:
            user_amount = gross * (10000 - (SKIM_BPS if skim_enabled else 0)) // 10000
            if treasury >= user_amount:
                treasury -= user_amount
            else:
                failed_claims += 1
                pending.append((_day + 1, gross))
        history.append(treasury)
    unpaid = sum(gross for _, gross in pending)
    return history, unpaid, failed_claims


def main():
    os.makedirs("out", exist_ok=True)
    rows = []
    series = {}
    for name, (taggers, delay) in SCENARIOS.items():
        with_skim, unpaid, failed = run(taggers, delay, True)
        without_skim, _, _ = run(taggers, delay, False)
        series[(name, "with skim")] = with_skim
        series[(name, "without skim")] = without_skim
        for label, values in (("with skim", with_skim), ("without skim", without_skim)):
            remaining = values[-1]
            rows.append((name, label, delay, START_TREASURY, remaining,
                         next((day for day, amount in enumerate(values) if amount == 0), ">60"),
                         unpaid if label == "with skim" else "n/a",
                         failed if label == "with skim" else "n/a"))
    with open("out/results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("scenario", "skim", "claim_delay_days", "seed_tokens",
                         "day_60_tokens", "depletion_day", "unpaid_gross_entitlement",
                         "failed_claim_attempts"))
        writer.writerows(rows)
    sweep_rows = []
    for name, (taggers, delay) in SCENARIOS.items():
        for hold_rate in HOLD_RATE_SWEEP:
            for seed_tokens in SEED_SWEEP:
                for pot_bps in POT_SWEEP_BPS:
                    values, unpaid, failed = run(
                        taggers, delay, True, pot_bps, seed_tokens, hold_rate)
                    sweep_rows.append((name, hold_rate, seed_tokens, pot_bps,
                                       delay, values[-1],
                                       values[-1] * 10000 // seed_tokens,
                                       unpaid, failed))
    with open("out/parameter_sweep.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("scenario", "hold_pts_per_token_day", "seed_tokens",
                         "daily_pot_bps", "claim_delay_days", "day_60_tokens",
                         "day_60_treasury_bps_of_seed", "unpaid_gross_entitlement",
                         "failed_claim_attempts"))
        writer.writerows(sweep_rows)
    # Portable SVG; no plotting dependency and easy to inspect in a browser.
    width, height, left, top = 900, 500, 70, 40
    colors = {"quiet": "#42d392", "expected": "#56a8ff", "raid-season": "#ffb454"}
    scale_x = 800 / DAYS
    scale_y = 390 / START_TREASURY
    paths = []
    for (name, skim), values in series.items():
        points = " ".join("%.1f,%.1f" % (left + day * scale_x,
                         top + (START_TREASURY - value) * scale_y)
                           for day, value in enumerate(values))
        dash = " stroke-dasharray='6 5'" if skim == "without skim" else ""
        paths.append("<polyline fill='none' stroke='%s' stroke-width='2'%s points='%s'/>" %
                     (colors[name], dash, points))
    tick = max(1, START_TREASURY // 10)
    labels = "".join("<text x='15' y='%d' fill='#b9c4d0' font-size='12'>%d</text>" %
                     (top + y * 39 + 4, START_TREASURY - y * tick) for y in range(11))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>" %
           (width, height, width, height) + "<rect width='100%' height='100%' fill='#101820'/>" +
           labels + "".join(paths) +
           "<text x='350' y='475' fill='#b9c4d0'>Day (60-day fixed-seed stress model)</text></svg>")
    with open("out/treasury.svg", "w") as f:
        f.write(svg)
    print("scenario,skim,claim_delay_days,seed_tokens,day_60_tokens,depletion_day,unpaid_gross_entitlement,failed_claim_attempts")
    for row in rows:
        print(",".join(map(str, row)))
    print("Parameter sweep: out/parameter_sweep.csv (0/25/50/100 hold points, 10/20/30% of 1,000,000-token supply as seed, 500/1,000/1,500 pot bps)")
    print("Recommendation: retain the owner-approved 50 hold points and 20% seed baseline pending real holder and claim data; this normalized model cannot identify production-optimal settings.")


if __name__ == "__main__":
    main()
