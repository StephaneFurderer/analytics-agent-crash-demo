"""Claims from a catastrophe event (the September 2026 Gulf Coast hurricane), drawn from the true model.

The event is hidden ground truth (ADR 0002): its claims go into the `claims` table like any other,
with nothing marking them as event claims. Only those reported by the Valuation date are kept.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from compass.generator.truth import Hurricane


def exposed_policies(policies: pd.DataFrame, bookings: pd.DataFrame, destinations: pd.DataFrame,
                     event: Hurricane) -> pd.DataFrame:
    """The Policies the event hits: policy_id, trip_cost, interrupted (on the trip at landfall, else cancelled)."""
    p = (policies.merge(bookings, on="booking_id", how="left")
         .merge(destinations[["destination_id", "region"]], on="destination_id", how="left"))
    landfall = pd.Timestamp(event.landfall)
    purchase, departure, ret = (pd.to_datetime(p[c]) for c in ("purchase_date", "departure_date", "return_date"))
    on_trip = (departure <= landfall) & (landfall <= ret)
    cancelled = (departure > landfall) & (departure <= landfall + pd.Timedelta(days=event.cancellation_window_days))
    hit = (p.region == event.region) & (purchase < landfall) & (on_trip | cancelled)
    return (p.loc[hit, ["policy_id", "trip_cost"]].assign(interrupted=on_trip[hit].to_numpy())
            .reset_index(drop=True))


def generate_hurricane_claims(rng: np.random.Generator, year: int, bookings: pd.DataFrame, policies: pd.DataFrame,
                              destinations: pd.DataFrame, event: Hurricane, reported_by: date | None) -> pd.DataFrame:
    """The event's claims on Underwriting year `year`'s Policies that are reported by `reported_by` (all if None).

    Same columns as the claims table, without claim ids: the caller numbers them together with
    the year's ordinary claims.
    """
    p = exposed_policies(policies[policies.booking_id.str.startswith(f"B{year}")], bookings, destinations, event)
    claimed = p[rng.random(len(p)) < event.claim_probability].reset_index(drop=True)
    n = len(claimed)
    trip_cost = claimed.trip_cost.to_numpy()

    share = np.where(claimed.interrupted, event.loss_share[0], event.loss_share[1])
    amount = rng.gamma(event.loss_shape, share * trip_cost / event.loss_shape)
    amount = np.minimum(np.round(np.maximum(amount, 0.01), 2), trip_cost)
    median, sigma = event.reporting_lag_days
    lag = np.round(rng.lognormal(np.log(median), sigma, n)).astype(int)
    loss = np.full(n, np.datetime64(event.landfall, "D"))
    report = loss + lag.astype("timedelta64[D]")

    claims = pd.DataFrame({
        "policy_id": claimed.policy_id.to_numpy(),
        "claim_type": np.where(claimed.interrupted, "post_departure", "pre_departure"),
        "loss_date": loss.astype(object),
        "report_date": report.astype(object),
        "paid_amount": amount,
        "case_reserve": 0.0,
    })
    if reported_by is not None:
        claims = claims[claims.report_date <= reported_by]
    return claims.reset_index(drop=True)
