"""Claims for one Underwriting year, drawn from the true model.

Per Policy, the number of claims is Poisson around the model's frequency. Each
claim is post-departure (delay, interruption) with the model's
`post_departure_share`, otherwise pre-departure (cancellation). Its amount is
Gamma around the model's severity mean for that claim type, capped at the trip
cost. Pre-departure claims occur between purchase and departure; post-departure
claims occur within the trip. Each claim is reported after a reporting lag, and
is paid in full when reported. Only claims reported by the Valuation date are kept.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from compass.generator.pricing import GLM, frequency, severity
from compass.generator.truth import ClaimProcess


def generate_claims(rng: np.random.Generator, year: int, bookings: pd.DataFrame, policies: pd.DataFrame,
                    destinations: pd.DataFrame, model: GLM, process: ClaimProcess,
                    valuation_date: date) -> pd.DataFrame:
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

    post = rng.random(n) < model.post_departure_share
    mean = severity(model, f, post)
    amount = rng.gamma(process.severity_shape, mean / process.severity_shape)
    amount = np.minimum(np.round(np.maximum(amount, 0.01), 2), f["trip_cost"])

    # Loss date: uniform over [purchase, departure) before departure, [departure, return] within the trip.
    start = np.where(post, departure[idx], purchase[idx])
    span = np.where(post, (ret[idx] - departure[idx]).astype(int) + 1,
                    (departure[idx] - purchase[idx]).astype(int))
    loss = start + np.floor(rng.random(n) * span).astype(int).astype("timedelta64[D]")
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
    claims = claims[claims.report_date <= np.datetime64(valuation_date)]
    claims = claims.sort_values(["report_date", "policy_id", "loss_date"], kind="stable").reset_index(drop=True)
    claims.insert(0, "claim_id", [f"C{year}-{i:06d}" for i in range(1, len(claims) + 1)])
    for column in ("loss_date", "report_date"):
        claims[column] = claims[column].to_numpy().astype("datetime64[D]").astype(object)
    return claims
