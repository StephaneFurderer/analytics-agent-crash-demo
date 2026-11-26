"""Bookings and Policies for one Underwriting year, vectorised with numpy."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from compass.generator import portfolio as pf
from compass.generator.destinations import DESTINATIONS
from compass.generator.pricing import PRICING_GLM_2025, pure_premium

# Departures are drawn over this many months from 1 January of the Underwriting
# year; a trip belongs to the year only if it was purchased in it.
DEPARTURE_WINDOW_MONTHS = 18


def destinations_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"destination_id": i, "city": city, "state_or_country": where, "region": region,
             "airport_code": airport, "hotel_rate": float(rate)}
            for i, (city, where, airport, region, rate) in enumerate(DESTINATIONS, start=1)
        ]
    )


def generate_year(rng: np.random.Generator, year: int, purchased_until: date,
                  destinations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bookings purchased between 1 January `year` and `purchased_until`, and their Policies."""
    parts = [
        _segment_bookings(rng, segment, n, year, purchased_until, destinations)
        for segment, n in pf.BOOKINGS_PER_YEAR.items()
    ]
    bookings = (pd.concat(parts, ignore_index=True)
                .sort_values(["purchase_date", "departure_date", "segment"], kind="stable")
                .reset_index(drop=True))
    bookings.insert(0, "booking_id", [f"B{year}-{i:06d}" for i in range(1, len(bookings) + 1)])
    policies = _policies(rng, bookings, destinations)
    return bookings, policies


def _segment_bookings(rng, segment, n, year, purchased_until, destinations) -> pd.DataFrame:
    start = np.datetime64(f"{year}-01-01")
    until = np.datetime64(purchased_until)
    chunks, have = [], 0
    while have < n:
        cand = _draw_trips(rng, segment, 2 * n, start)
        keep = (cand["purchase_date"] >= start) & (cand["purchase_date"] <= until)
        chunk = {k: v[keep] for k, v in cand.items()}
        chunks.append(chunk)
        have += int(keep.sum())
    trips = {k: np.concatenate([c[k] for c in chunks])[:n] for k in chunks[0]}

    region_names = np.array(["us_atlantic", "gulf_coast", "caribbean"])
    region = rng.choice(region_names, size=n, p=pf.REGION_WEIGHTS[segment])
    destination_id = np.empty(n, dtype=int)
    for r in region_names:
        ids = destinations.loc[destinations.region == r, "destination_id"].to_numpy()
        mask = region == r
        destination_id[mask] = rng.choice(ids, size=int(mask.sum()))

    state_p = np.array(pf.STATE_WEIGHTS[segment])
    return pd.DataFrame({
        "segment": segment,
        "destination_id": destination_id,
        "age": _ages(rng, segment, n),
        "state_of_residence": rng.choice(pf.STATES, size=n, p=state_p / state_p.sum()),
        "coverage_type": rng.choice(pf.COVERAGE_TYPES, size=n, p=pf.COVERAGE_WEIGHTS[segment]),
        "purchase_date": trips["purchase_date"].astype("datetime64[D]").astype(object),
        "departure_date": trips["departure_date"].astype("datetime64[D]").astype(object),
        "return_date": trips["return_date"].astype("datetime64[D]").astype(object),
        "num_nights": trips["num_nights"],
    })


def _draw_trips(rng, segment, n, start) -> dict[str, np.ndarray]:
    """Departure dates with the segment's seasonality, then nights and advance purchase."""
    months = np.arange(DEPARTURE_WINDOW_MONTHS)
    weights = np.array([pf.MONTH_WEIGHTS[segment][m % 12] for m in months])
    month_offset = rng.choice(months, size=n, p=weights / weights.sum())
    month_start = start.astype("datetime64[M]") + month_offset.astype("timedelta64[M]")
    days_in_month = ((month_start + np.timedelta64(1, "M")).astype("datetime64[D]") - month_start.astype("datetime64[D]")).astype(int)
    departure = month_start.astype("datetime64[D]") + np.floor(rng.random(n) * days_in_month).astype("timedelta64[D]")

    median, sigma, lo, hi = pf.NIGHTS[segment]
    nights = np.clip(np.round(rng.lognormal(np.log(median), sigma, n)), lo, hi).astype(int)
    mean, std, lo, hi = pf.ADVANCE_DAYS[segment]
    advance = np.clip(np.round(rng.normal(mean, std, n)), lo, hi).astype(int)
    return {
        "departure_date": departure,
        "return_date": departure + nights.astype("timedelta64[D]"),
        "purchase_date": departure - advance.astype("timedelta64[D]"),
        "num_nights": nights,
    }


def _ages(rng, segment, n) -> np.ndarray:
    mean, std, lo, hi = pf.AGE[segment]
    if mean is None:
        return rng.integers(lo, hi + 1, size=n)
    return np.clip(np.round(rng.normal(mean, std, n)), lo, hi).astype(int)


def _policies(rng, bookings: pd.DataFrame, destinations: pd.DataFrame) -> pd.DataFrame:
    dest = destinations.set_index("destination_id").loc[bookings.destination_id]
    departure = pd.to_datetime(bookings.departure_date)
    month = departure.dt.month.to_numpy()
    peak = np.isin(month, pf.PEAK_MONTHS)
    advance = (departure - pd.to_datetime(bookings.purchase_date)).dt.days.to_numpy()
    n = len(bookings)

    hotel_rate = dest.hotel_rate.to_numpy() * (1 + pf.HOTEL_PEAK_UPLIFT * peak) * rng.uniform(*pf.HOTEL_RATE_NOISE, n)
    hotel_cost = np.round(np.round(hotel_rate, 2) * bookings.num_nights.to_numpy(), 2)
    caribbean = dest.region.to_numpy() == "caribbean"
    fare = np.where(caribbean, rng.uniform(*pf.FLIGHT_FARE["caribbean"], n), rng.uniform(*pf.FLIGHT_FARE["other"], n))
    flight_cost = np.round(
        fare * (1 + pf.FLIGHT_PEAK_UPLIFT * peak) * (1 - pf.FLIGHT_ADVANCE_DISCOUNT * np.minimum(advance, 180) / 180), 2
    )

    frames = []
    for product, suffix, costs, covered in [
        ("hotel", "H", hotel_cost, bookings.coverage_type.isin(["hotel_only", "hotel_and_flight"]).to_numpy()),
        ("flight", "F", flight_cost, bookings.coverage_type.isin(["flight_only", "hotel_and_flight"]).to_numpy()),
    ]:
        b = bookings[covered]
        frames.append(pd.DataFrame({
            "policy_id": b.booking_id + "-" + suffix,
            "booking_id": b.booking_id,
            "product": product,
            "trip_cost": costs[covered],
            "_order": np.flatnonzero(covered) * 2 + (suffix == "F"),
            # Rating features, used to price the Policy (not stored).
            "_age": b.age.to_numpy(),
            "_segment": b.segment.to_numpy(),
            "_state": b.state_of_residence.to_numpy(),
            "_month": month[covered],
            "_region": dest.region.to_numpy()[covered],
        }))
    policies = pd.concat(frames).sort_values("_order").reset_index(drop=True)

    features = {
        "age": policies._age.to_numpy(), "trip_cost": policies.trip_cost.to_numpy(),
        "product": policies["product"].to_numpy(), "segment": policies._segment.to_numpy(),
        "state_of_residence": policies._state.to_numpy(), "departure_month": policies._month.to_numpy(),
        "region": policies._region.to_numpy(),
    }
    pure = np.round(pure_premium(PRICING_GLM_2025, features), 2)
    policies["pure_premium"] = pure
    policies["commercial_premium"] = np.round(pure * PRICING_GLM_2025.expense_load, 2)
    return policies[[c for c in policies.columns if not c.startswith("_")]]
