"""Performance tab: Ultimate, Loss ratio and A/E on the standard development factors.

A/E is shown by segment and departure month only: the Legacy dashboard has no geographic A/E view.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics
from compass.dashboard import display

OVERVIEW = ["incurred", "ibnr", "ultimate", "loss_ratio", "ae"]
BREAKDOWN = ["earned_pure_premium", "incurred", "ibnr", "ultimate", "ultimate_claim_count",
             "ultimate_frequency", "ultimate_severity", "loss_ratio", "ae"]
BAND = "A/E band"


def render(con, catalogue: pd.DataFrame) -> None:
    st.header("Performance")
    bands = metrics.ae_bands(con)
    st.caption("Ultimate = Incurred + IBNR, on the standard development factors. A/E = Ultimate / earned Pure "
               "premium (Pricing basis). Bands: " + "; ".join(bands.description))
    display.tiles(metrics.query(con, OVERVIEW).iloc[0], catalogue)

    st.subheader("By underwriting year")
    _table(con, catalogue, "underwriting_year")

    st.subheader("A/E by segment")
    _table(con, catalogue, "segment")

    st.subheader("A/E by departure month")
    _table(con, catalogue, "departure_month", ["earned_pure_premium", "ultimate", "ae"])


def _table(con, catalogue: pd.DataFrame, by: str, columns: list[str] = BREAKDOWN) -> None:
    frame = metrics.query(con, columns, by=[by])
    frame[BAND] = [metrics.ae_band(con, ae) if pd.notna(ae) else "–" for ae in frame.ae]
    display.table(frame, catalogue)
