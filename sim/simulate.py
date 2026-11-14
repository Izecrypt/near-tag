"""A transparent, seeded 60-day treasury stress model (not a forecast)."""
import csv
import os
import random

DAYS = 60
SEED = 20261114
START_TREASURY = 1_000_000
POT_BPS = 1000
POT_SWEEP_BPS = (500, 1000, 1500)
SEED_SWEEP = (100_000, 200_000, 300_000)
SKIM_BPS = 500
SCENARIOS = {"quiet": (20, 3), "expected": (150, 1), "raid-season": (800, 0)}


def run(taggers, claim_delay, skim_enabled, pot_bps=POT_BPS,
        start_treasury=START_TREASURY):
    rng = random.Random(SEED + taggers)
    treasury = start_treasury
    history = [treasury]
    pending = []
    failed_claims = 0
    for _day in range(1, DAYS + 1):
        available = max(0, treasury - sum(gross for _, gross in pending))
        pot = min(available * pot_bps // 10000, available)
        validator_cut = pot // 10
        user_budget = pot - validator_cut
        scores = [rng.randint(100, 10000) for _ in range(taggers)]
        balances = [rng.randint(100, 50000) for _ in range(taggers)]
        total_score = sum(scores)
        paid = 0
        if total_score:
            for score, balance in zip(scores, balances):
                share = user_budget * score // total_score
                paid += min(share, balance)
        paid += validator_cut
        paid = min(paid, pot)
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
        for seed_tokens in SEED_SWEEP:
            for pot_bps in POT_SWEEP_BPS:
                values, unpaid, failed = run(taggers, delay, True, pot_bps,
                                             seed_tokens)
                sweep_rows.append((name, seed_tokens, pot_bps, delay,
                                   values[-1], values[-1] * 10000 // seed_tokens,
                                   unpaid, failed))
    with open("out/parameter_sweep.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(("scenario", "seed_tokens", "daily_pot_bps",
                         "claim_delay_days", "day_60_tokens",
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
    labels = "".join("<text x='15' y='%d' fill='#b9c4d0' font-size='12'>%d</text>" %
                     (top + y * 39 + 4, START_TREASURY - y * 100000) for y in range(11))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>" %
           (width, height, width, height) + "<rect width='100%' height='100%' fill='#101820'/>" +
           labels + "".join(paths) +
           "<text x='350' y='475' fill='#b9c4d0'>Day (60-day fixed-seed stress model)</text></svg>")
    with open("out/treasury.svg", "w") as f:
        f.write(svg)
    print("scenario,skim,claim_delay_days,seed_tokens,day_60_tokens,depletion_day,unpaid_gross_entitlement,failed_claim_attempts")
    for row in rows:
        print(",".join(map(str, row)))
    print("Parameter sweep: out/parameter_sweep.csv (10%, 20%, 30% seed; 500, 1,000, 1,500 pot bps)")
    print("Recommendation: retain 20% seed and 1,000 bps pending real claim and holder data; this normalized model cannot identify production-optimal settings.")


if __name__ == "__main__":
    main()
