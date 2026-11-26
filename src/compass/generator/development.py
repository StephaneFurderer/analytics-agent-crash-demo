"""Derive the standard development factors from the reporting-lag pattern. Run offline.

    uv run python -m compass.generator.development > src/compass/assumptions/development_factors.csv

The output is version-controlled assumption data: the Metric layer reads the CSV, never this
module (ADR 0002), and an actuary may edit the CSV by hand. This is only how the first selection
was made.

Method: simulate 2025-style books under several seeds with every claim eventually reported, and
for each maturity m (whole months from the departure month to a Valuation month) place a
hypothetical Valuation date at the end of the month m months after each claim's departure month.
The factor is (claims occurred by then) / (claims reported by then), pooled over all claims, for
counts and for amounts. It reflects the reporting lag and the timing of losses around departure
only, never the level of claims, so the 2026 Drift and the hurricane do not enter it.
"""

from __future__ import annotations

import sys
from datetime import date

import numpy as np
import pandas as pd

from compass.generator import STREAM_BOOKINGS, STREAM_CLAIMS, rng_for
from compass.generator.book import destinations_frame, generate_year
from compass.generator.claims import generate_claims
from compass.generator.truth import CLAIM_PROCESS, TRUE_MODEL

SEEDS = range(1000, 1010)  # not the demo's seed: the factors are a selection, not a fit to the book
YEAR = 2025
MATURITIES = range(-6, 25)
TAIL_TOLERANCE = 0.0005  # factors this close to 1 are selected as 1 (fully developed)


def simulated_claims(seeds=SEEDS) -> pd.DataFrame:
    """Every claim of 2025-style books (nothing cut off at a Valuation date), with departure dates."""
    destinations = destinations_frame()
    frames = []
    for seed in seeds:
        bookings, policies = generate_year(rng_for(seed, YEAR, STREAM_BOOKINGS), YEAR, date(YEAR, 12, 31),
                                           destinations)
        claims = generate_claims(rng_for(seed, YEAR, STREAM_CLAIMS), YEAR, bookings, policies, destinations,
                                 TRUE_MODEL[YEAR], CLAIM_PROCESS, date(2100, 1, 1))
        departures = policies.merge(bookings, on="booking_id")[["policy_id", "departure_date"]]
        frames.append(claims.merge(departures, on="policy_id"))
    return pd.concat(frames, ignore_index=True)


def derive(claims: pd.DataFrame, maturities=MATURITIES) -> pd.DataFrame:
    """Selected factors by maturity: count_factor and amount_factor (Ultimate / Incurred)."""
    departure_month = pd.to_datetime(claims.departure_date).dt.to_period("M")
    loss = pd.to_datetime(claims.loss_date)
    report = pd.to_datetime(claims.report_date)
    amount = claims.paid_amount.to_numpy()
    rows = []
    for m in maturities:
        valuation = (departure_month + m).dt.to_timestamp(how="end").dt.normalize()
        occurred = (loss <= valuation).to_numpy()
        reported = (report <= valuation).to_numpy()
        if reported.sum() == 0:
            continue
        rows.append({"maturity_months": m,
                     "count_factor": occurred.sum() / reported.sum(),
                     "amount_factor": amount[occurred].sum() / amount[reported].sum()})
    factors = pd.DataFrame(rows)
    for column in ("count_factor", "amount_factor"):
        f = factors[column].to_numpy()
        f = np.maximum.accumulate(f[::-1])[::-1]  # never increasing with maturity
        factors[column] = np.where(f - 1 < TAIL_TOLERANCE, 1.0, np.round(f, 3))
    developed = factors[(factors.count_factor == 1.0) & (factors.amount_factor == 1.0)]
    if len(developed):  # keep one fully developed row: later maturities use it
        factors = factors[factors.maturity_months <= developed.maturity_months.min()]
    return factors.reset_index(drop=True)


HEADER = """\
# Standard development factors (Ultimate / Incurred), selected separately for claim counts and amounts.
# Expert-judgment assumption data: edit by hand and commit. The Metric layer reads this file.
# maturity_months: whole months from a Policy's departure month to the Valuation month
#   (0 = departs in the Valuation month, negative = not departed yet). A Policy uses the row with the
#   largest maturity at or below its own (the first row if none); the last row (1.000) is fully developed.
# First selection: derived offline from the reporting-lag pattern by `python -m compass.generator.development`.
"""


def main() -> None:
    sys.stdout.write(HEADER)
    derive(simulated_claims()).to_csv(sys.stdout, index=False, float_format="%.3f")


if __name__ == "__main__":
    main()
