"""Claims for one Underwriting year, drawn from the true model.

Per Policy, the number of claims is Poisson around the model's frequency. Each
claim's loss date is uniform over the cover period (purchase to return, both days
included), as premium is earned: it is pre-departure (cancellation) before the
departure date, post-departure (delay, interruption) from it. Its amount is Gamma
around the model's severity mean for that claim type, capped at the trip cost.
Each claim is reported after a reporting lag, and
is paid in full when reported. Only claims reported by `reported_by` (the Valuation date) are kept;
`None` keeps every claim.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from compass.generator.pricing import GLM, cover_days, frequency, severity
from compass.generator.truth import ClaimProcess


def generate_claims(rng: np.random.Generator, year: int, bookings: pd.DataFrame, policies: pd.DataFrame,
                    destinations: pd.DataFrame, model: GLM, process: ClaimProcess,
                    reported_by: date | None) -> pd.DataFrame:
    p = (policies.merge(bookings, on="booking_id", how="left")
         .merge(destinations[["destination_id", "region"]], on="destination_id", how="left"))
    purchase = pd.to_datetime(p.purchase_date).to_numpy().astype("datetime64[D]")
    departure = pd.to_datetime(p.departure_date).to_numpy().astype("datetime64[D]")
    ret = pd.to_datetime(p.return_date).to_numpy().astype("datetime64[D]")
    features = {
        "age": p.age.to_numpy(), "trip_cost": p.trip_cost.to_numpy(), "product": p["product"].to_numpy(),
        "segment": p.segment.to_numpy(), "state_of_residence": p.state_of_residence.to_numpy(),
        "departure_month": (departure.astype("datetime64[M]").astype(int) % 12) + 1,
        "region": p.region.to_numpy(),
    }

    counts = rng.poisson(frequency(model, features))
    idx = np.repeat(np.arange(len(p)), counts)
    n = len(idx)
    f = {k: v[idx] for k, v in features.items()}

    # Loss date: uniform over the cover period's days; on or after departure it is a post-departure claim.
    span = cover_days(purchase[idx], ret[idx])
    loss = purchase[idx] + np.floor(rng.random(n) * span).astype(int).astype("timedelta64[D]")
    post = loss >= departure[idx]
    mean = severity(model, f, post)
    amount = rng.gamma(process.severity_shape, mean / process.severity_shape)
    amount = np.minimum(np.round(np.maximum(amount, 0.01), 2), f["trip_cost"])

    median, sigma = process.reporting_lag_days
    lag = np.round(rng.lognormal(np.log(median), sigma, n)).astype(int)
    report = loss + lag.astype("timedelta64[D]")

    claims = pd.DataFrame({
        "policy_id": p.policy_id.to_numpy()[idx],
        "claim_type": np.where(post, "post_departure", "pre_departure"),
        "loss_date": loss,
        "report_date": report,
        "paid_amount": amount,
        "case_reserve": 0.0,
    })
    if reported_by is not None:
        claims = claims[claims.report_date <= np.datetime64(reported_by)]
    return number_claims(claims, year)


def number_claims(claims: pd.DataFrame, year: int) -> pd.DataFrame:
    """Sort one Underwriting year's claims by report date and give them ids C<year>-000001, ..."""
    claims = claims.drop(columns="claim_id", errors="ignore")
    for column in ("loss_date", "report_date"):
        claims[column] = pd.to_datetime(claims[column]).to_numpy().astype("datetime64[D]")
    claims = claims.sort_values(["report_date", "policy_id", "loss_date"], kind="stable").reset_index(drop=True)
    claims.insert(0, "claim_id", [f"C{year}-{i:06d}" for i in range(1, len(claims) + 1)])
    for column in ("loss_date", "report_date"):
        claims[column] = claims[column].to_numpy().astype("datetime64[D]").astype(object)
    return claims
