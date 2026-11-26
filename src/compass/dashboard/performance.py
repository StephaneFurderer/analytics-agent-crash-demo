"""Performance tab: Ultimate, Loss ratio and A/E on the standard development factors.

A/E is shown by Underwriting year, then by segment and departure month for one Underwriting year at a time
(so immature 2026 isn't pooled with mature 2025). The Legacy dashboard has no geographic A/E view.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics
from compass.dashboard import display

OVERVIEW = ["incurred", "ibnr", "ultimate", "loss_ratio", "ae"]
BREAKDOWN = ["earned_pure_premium", "incurred", "ibnr", "ultimate", "ultimate_claim_count",
             "ultimate_frequency", "ultimate_severity", "loss_ratio", "ae"]
AE_BAND_COLUMN = "A/E band"
YEAR_KEY = "performance_underwriting_year"  # the Underwriting year picker's widget key


def render(con, catalogue: pd.DataFrame) -> None:
    st.header("Performance")
    bands = metrics.ae_bands(con)
    st.caption("Ultimate = Incurred + IBNR, on the standard development factors. A/E = Ultimate / earned Pure "
               "premium (Pricing basis). Bands: " + "; ".join(bands.description))
    display.tiles(metrics.query(con, OVERVIEW).iloc[0], catalogue)

    st.subheader("By underwriting year")
    by_year = _table(con, catalogue, ["underwriting_year"])

    years = sorted(int(y) for y in by_year.underwriting_year)
    year = st.selectbox("Underwriting year", years, index=len(years) - 1, key=YEAR_KEY)
    where = f"underwriting_year = {int(year)}"

    st.subheader(f"A/E by segment, underwriting year {year}")
    _table(con, catalogue, ["segment"], where=where)

    st.subheader(f"A/E by departure month, underwriting year {year}")
    _table(con, catalogue, ["departure_month"], ["earned_pure_premium", "ultimate", "ae"], where=where)


def _table(con, catalogue: pd.DataFrame, by: list[str], columns: list[str] = BREAKDOWN,
           where: str | None = None) -> pd.DataFrame:
    frame = metrics.query(con, columns, by=by, where=where)
    frame[AE_BAND_COLUMN] = [metrics.ae_band(con, ae) if pd.notna(ae) else "–" for ae in frame.ae]
    display.table(frame, catalogue)
    return frame
