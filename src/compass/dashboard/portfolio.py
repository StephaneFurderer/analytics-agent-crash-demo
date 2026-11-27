"""Portfolio tab: volumes, premium and claims."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics
from compass.dashboard import display

VOLUME_AND_PREMIUM = ["booking_count", "policy_count", "written_pure_premium", "written_commercial_premium"]
EARNED_AND_CLAIMS = ["earned_pure_premium", "earned_commercial_premium", "reported_claim_count", "incurred"]
OVERVIEW = VOLUME_AND_PREMIUM + EARNED_AND_CLAIMS


def render(con, catalogue: pd.DataFrame) -> None:
    st.header("Portfolio")
    display.tiles(metrics.query(con, VOLUME_AND_PREMIUM).iloc[0], catalogue)
    display.tiles(metrics.query(con, EARNED_AND_CLAIMS).iloc[0], catalogue)

    st.subheader("By underwriting year")
    display.table(metrics.query(con, OVERVIEW, by=["underwriting_year"]), catalogue)

    left, right = st.columns(2)
    with left:
        st.subheader("By segment")
        display.table(metrics.query(con, OVERVIEW, by=["segment"]), catalogue)
    with right:
        st.subheader("By coverage")
        display.table(metrics.query(con, OVERVIEW, by=["coverage_type"]), catalogue)

    st.subheader("By product")
    display.table(metrics.query(con, OVERVIEW, by=["product"]), catalogue)

    # One series per Underwriting year: a 2025 and a 2026 purchase departing in the same month are different books.
    st.subheader("Bookings by departure month and underwriting year")
    by_month = metrics.query(con, ["booking_count"], by=["departure_month", "underwriting_year"])
    by_month["underwriting_year"] = by_month.underwriting_year.astype(str)
    st.bar_chart(by_month, x="departure_month", y="booking_count", color="underwriting_year", stack=False)
