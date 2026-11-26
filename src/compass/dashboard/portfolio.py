"""Portfolio tab: volumes and written premium."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics
from compass.dashboard import display

VOLUME_AND_PREMIUM = ["booking_count", "policy_count", "written_pure_premium", "written_commercial_premium"]


def render(con, catalogue: pd.DataFrame) -> None:
    st.header("Portfolio")
    display.tiles(metrics.query(con, VOLUME_AND_PREMIUM).iloc[0], catalogue)

    left, right = st.columns(2)
    with left:
        st.subheader("By segment")
        display.table(metrics.query(con, VOLUME_AND_PREMIUM, by=["segment"]), catalogue)
    with right:
        st.subheader("By coverage")
        display.table(metrics.query(con, VOLUME_AND_PREMIUM, by=["coverage_type"]), catalogue)

    st.subheader("By product")
    display.table(metrics.query(con, VOLUME_AND_PREMIUM, by=["product"]), catalogue)

    st.subheader("Bookings by departure month")
    by_month = metrics.query(con, ["booking_count"], by=["departure_month"])
    st.bar_chart(by_month.set_index("departure_month")["booking_count"])
