"""The seeded generator of Compass Assistance's book.

`generate_book(seed)` returns the warehouse's base tables as DataFrames. It is a
pure function of the seed: every random draw comes from a stream keyed by
(seed, Underwriting year, stream), so adding a new stream later (claims, a new
year) does not change the data the existing streams produce.

Module map:
- `portfolio`: how the book is sold (segments, mixes, seasonality, trip costs)
- `destinations`: the 38 destinations
- `pricing`: the Pricing basis, the 2025 pricing GLM (may go into the warehouse)
- `truth`: the true model (hidden ground truth, ADR 0002)
- `book`: Bookings and Policies for one Underwriting year
- `claims`: claims for one Underwriting year from the true model, reported by the Valuation date
- `hurricane`: the September 2026 Gulf Coast hurricane's claims (true model; mostly reported after the Valuation date)
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import date

import numpy as np
import pandas as pd

from compass.generator.book import destinations_frame, generate_year
from compass.generator.claims import generate_claims, number_claims
from compass.generator.hurricane import generate_hurricane_claims
from compass.generator.truth import CLAIM_PROCESS, HURRICANE, TRUE_MODEL
from compass.generator.pricing import PRICING_GLM_2025, coefficients_frame

VALUATION_DATE = date(2026, 9, 30)  # must match valuation_date() in metrics/sql/05_valuation.sql
UNDERWRITING_YEARS = (2025, 2026)

# Seeds the offline calibrations (development factors, hurricane loading) simulate: not the demo's seed,
# since the assumptions are a selection, not a fit to the book.
CALIBRATION_SEEDS = range(1000, 1010)

# Stream ids: append new ones, never renumber.
STREAM_BOOKINGS = 1
STREAM_CLAIMS = 2
STREAM_HURRICANE = 3


def rng_for(seed: int, year: int, stream: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed, year, stream]))


# The two sources of claims: the true model's ordinary claims and the September 2026 hurricane's.
CLAIM_SOURCES = ("ordinary", "hurricane")


def generate_book(seed: int, reported_by: date | None = VALUATION_DATE,
                  claims: Collection[str] = CLAIM_SOURCES) -> dict[str, pd.DataFrame]:
    """The warehouse's base tables for `seed`, as DataFrames.

    The book is sold up to the Valuation date. `reported_by` keeps the claims reported by that date
    (the warehouse); `None` keeps every claim, the fully developed book the generator's tests compare
    against. `claims` picks the sources of claims (`CLAIM_SOURCES`); the draws don't depend on it.
    """
    unknown = set(claims) - set(CLAIM_SOURCES)
    if unknown:
        raise ValueError(f"unknown claim sources: {sorted(unknown)}")
    destinations = destinations_frame()
    bookings, policies, all_claims = [], [], []
    for year in UNDERWRITING_YEARS:
        purchased_until = min(date(year, 12, 31), VALUATION_DATE)
        b, p = generate_year(rng_for(seed, year, STREAM_BOOKINGS), year, purchased_until, destinations)
        sources = []
        if "ordinary" in claims:
            sources.append(generate_claims(rng_for(seed, year, STREAM_CLAIMS), year, b, p, destinations,
                                           TRUE_MODEL[year], CLAIM_PROCESS, reported_by))
        # The hurricane hits trips of any Underwriting year in progress or about to depart (e.g. 2025 sales
        # for September 2026 trips); its claims are numbered among the year's ordinary claims.
        if "hurricane" in claims:
            sources.append(generate_hurricane_claims(rng_for(seed, year, STREAM_HURRICANE), year, b, p,
                                                     destinations, HURRICANE, reported_by))
        bookings.append(b)
        policies.append(p)
        all_claims.append(number_claims(pd.concat(sources, ignore_index=True), year))
    return {
        "destinations": destinations,
        "bookings": pd.concat(bookings, ignore_index=True),
        "policies": pd.concat(policies, ignore_index=True),
        "claims": pd.concat(all_claims, ignore_index=True),
        "pricing_coefficients": coefficients_frame(PRICING_GLM_2025),
    }
