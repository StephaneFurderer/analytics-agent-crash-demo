"""Calibrate the hurricane loading's first selection. Run offline.

    uv run python -m compass.generator.hurricane_loading > src/compass/assumptions/hurricane_loading.csv

The output is version-controlled Expert-judgment assumption data: the Metric layer reads the CSV,
never this module (ADR 0002), and an actuary may edit the CSV by hand. This is only how the first
estimate was made, standing in for the actuary's catastrophe estimate.

Method: simulate books under several seeds (not the demo's) with every event claim eventually
reported. The loading is what the event adds on top of the chain-ladder Ultimate: all its claims,
minus the event claims already reported by the Valuation date developed with the standard factors.
It is spread over the Policies at risk in the region on the event date (purchase <= date <= return):
per Policy for counts, per unit of trip cost for amounts.
"""

from __future__ import annotations

import sys
from datetime import date

import numpy as np
import pandas as pd

from compass import metrics
from compass.generator import STREAM_BOOKINGS, STREAM_HURRICANE, UNDERWRITING_YEARS, VALUATION_DATE, rng_for
from compass.generator.book import destinations_frame, generate_year
from compass.generator.hurricane import generate_hurricane_claims
from compass.generator.truth import HURRICANE

SEEDS = range(1000, 1010)
EVENT = "September 2026 Gulf Coast hurricane"


def _factor(maturity: np.ndarray, factors: pd.DataFrame, column: str) -> np.ndarray:
    """The standard factor for each maturity: the row with the largest maturity at or below it, else the first."""
    m = factors.maturity_months.to_numpy()
    idx = np.clip(np.searchsorted(m, maturity, side="right") - 1, 0, len(m) - 1)
    return factors[column].to_numpy()[idx]


def calibrate(seeds=SEEDS) -> dict:
    destinations = destinations_frame()
    factors = metrics.standard_development_factors().sort_values("maturity_months")
    landfall = pd.Timestamp(HURRICANE.landfall)
    valuation_month = pd.Timestamp(VALUATION_DATE).to_period("M")
    claims_needed = amount_needed = policies_at_risk = trip_cost_at_risk = 0.0
    for seed in seeds:
        for year in UNDERWRITING_YEARS:
            purchased_until = min(date(year, 12, 31), VALUATION_DATE)
            b, p = generate_year(rng_for(seed, year, STREAM_BOOKINGS), year, purchased_until, destinations)
            every = generate_hurricane_claims(rng_for(seed, year, STREAM_HURRICANE), year, b, p, destinations,
                                              HURRICANE, date(2100, 1, 1))
            pb = p.merge(b, on="booking_id").merge(destinations[["destination_id", "region"]], on="destination_id")
            at_risk = ((pb.region == HURRICANE.region) & (pd.to_datetime(pb.purchase_date) <= landfall)
                       & (landfall <= pd.to_datetime(pb.return_date)))
            policies_at_risk += at_risk.sum()
            trip_cost_at_risk += pb.trip_cost[at_risk].sum()

            reported = every[pd.to_datetime(every.report_date) <= pd.Timestamp(VALUATION_DATE)]
            departure = pd.to_datetime(reported.merge(pb[["policy_id", "departure_date"]], on="policy_id")
                                       .departure_date)
            maturity = np.array([(valuation_month - d.to_period("M")).n for d in departure], dtype=int)
            claims_needed += len(every) - _factor(maturity, factors, "count_factor").sum()
            amount_needed += (every.paid_amount.sum()
                              - (reported.paid_amount.to_numpy() * _factor(maturity, factors, "amount_factor")).sum())
    return {"event": EVENT, "destination_region": HURRICANE.region, "event_date": HURRICANE.landfall.isoformat(),
            "count_per_policy": round(claims_needed / policies_at_risk, 4),
            "amount_per_trip_cost": round(amount_needed / trip_cost_at_risk, 4)}


HEADER = """\
# Hurricane loading: Expert-judgment estimate of an event's claims not yet in Ultimate. Kept separate from the
# standard development factors (development_factors.csv); edit by hand and commit. The Metric layer reads this file
# and applies it only in the *_with_loading metrics: Ultimate, A/E and Loss ratio stay unloaded by default.
# One row per event. A Policy is at risk on event_date if purchased on or before it and returning on or after it.
#   count_per_policy: expected claims per Policy at risk in destination_region on event_date
#   amount_per_trip_cost: expected losses per unit of trip cost at risk there
# Both are net of the event claims already reported (and developed by the standard factors) at the Valuation date.
# First selection: calibrated offline by `python -m compass.generator.hurricane_loading`.
"""


def main() -> None:
    sys.stdout.write(HEADER)
    pd.DataFrame([calibrate()]).to_csv(sys.stdout, index=False)


if __name__ == "__main__":
    main()
