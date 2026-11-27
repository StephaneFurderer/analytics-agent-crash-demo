"""Calibrate the hurricane loading's first selection. Run offline.

    uv run python -m compass.generator.hurricane_loading > src/compass/assumptions/hurricane_loading.csv

The output is version-controlled Expert-judgment assumption data: the Metric layer reads the CSV,
never this module (ADR 0002), and an actuary may edit the CSV by hand. This is only how the first
estimate was made, standing in for the actuary's catastrophe estimate.

Method: simulate books under several seeds (not the demo's) with every event claim eventually
reported. The loading is what the event adds on top of the chain-ladder Ultimate: all its claims,
minus the Metric layer's Ultimate on a warehouse holding only the event claims reported by the
Valuation date (so they are developed exactly as the Metric layer develops them). It is spread over
the Metric layer's Exposure in the region on the event date: per Policy for counts, per unit of
trip cost for amounts.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

from compass import metrics, warehouse
from compass.generator import CALIBRATION_SEEDS, VALUATION_DATE, generate_book
from compass.generator.truth import HURRICANE

EVENT_NAME = "September 2026 Gulf Coast hurricane"


def calibrate(seeds=CALIBRATION_SEEDS) -> dict:
    """The loading's row: what the event adds on top of the Metric layer's chain-ladder Ultimate, per unit at risk."""
    claims_needed = amount_needed = policies_at_risk = trip_cost_at_risk = 0.0
    in_region = f"destination_region = '{HURRICANE.region}'"
    with tempfile.TemporaryDirectory() as tmp:
        for seed in seeds:
            # The event's claims alone, every one of them; the warehouse holds those reported by the Valuation date.
            book = generate_book(seed, reported_by=None, claims=("hurricane",))
            every = book["claims"]
            book["claims"] = every[every.report_date <= VALUATION_DATE]
            path = warehouse.write(Path(tmp) / f"seed{seed}.duckdb", **book)
            con = metrics.connect(path)
            try:
                developed = metrics.query(con, ["ultimate", "ultimate_claim_count"], where=in_region).iloc[0]
                at_risk = metrics.exposure(con, HURRICANE.landfall, where=in_region).iloc[0]
            finally:
                con.close()
            claims_needed += len(every) - developed.ultimate_claim_count
            amount_needed += every.paid_amount.sum() - developed.ultimate
            policies_at_risk += at_risk.policies_at_risk
            trip_cost_at_risk += at_risk.exposure
    return {"event": EVENT_NAME, "destination_region": HURRICANE.region,
            "event_date": HURRICANE.landfall.isoformat(),
            "count_per_policy": round(float(claims_needed / policies_at_risk), 4),
            "amount_per_trip_cost": round(float(amount_needed / trip_cost_at_risk), 4)}


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
