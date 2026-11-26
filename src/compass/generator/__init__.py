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
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from compass.generator.book import destinations_frame, generate_year
from compass.generator.claims import generate_claims
from compass.generator.truth import CLAIM_PROCESS, TRUE_MODEL

VALUATION_DATE = date(2026, 9, 30)  # must match valuation_date() in metrics/sql/05_valuation.sql
UNDERWRITING_YEARS = (2025,)

# Stream ids: append new ones, never renumber.
STREAM_BOOKINGS = 1
STREAM_CLAIMS = 2


def rng_for(seed: int, year: int, stream: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed, year, stream]))


def generate_book(seed: int) -> dict[str, pd.DataFrame]:
    destinations = destinations_frame()
    bookings, policies, claims = [], [], []
    for year in UNDERWRITING_YEARS:
        purchased_until = min(date(year, 12, 31), VALUATION_DATE)
        b, p = generate_year(rng_for(seed, year, STREAM_BOOKINGS), year, purchased_until, destinations)
        c = generate_claims(rng_for(seed, year, STREAM_CLAIMS), year, b, p, destinations,
                            TRUE_MODEL[year], CLAIM_PROCESS, VALUATION_DATE)
        bookings.append(b)
        policies.append(p)
        claims.append(c)
    return {
        "destinations": destinations,
        "bookings": pd.concat(bookings, ignore_index=True),
        "policies": pd.concat(policies, ignore_index=True),
        "claims": pd.concat(claims, ignore_index=True),
    }
