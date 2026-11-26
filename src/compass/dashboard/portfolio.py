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

    st.subheader("Bookings by departure month")
    by_month = metrics.query(con, ["booking_count"], by=["departure_month"])
    st.bar_chart(by_month.set_index("departure_month")["booking_count"])
