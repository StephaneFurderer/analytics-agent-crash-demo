"""Compass Assistance Legacy dashboard. Run with `uv run demo dashboard`.

Each tab is a module with a `render(con, catalogue)` function. Later tabs
(Pricing, Performance) are added to TABS in display order.
"""

import streamlit as st

from compass import metrics, warehouse
from compass.dashboard import portfolio, pricing

TABS = [("Pricing", pricing.render), ("Portfolio", portfolio.render)]

st.set_page_config(page_title="Compass Assistance | Portfolio dashboard", layout="wide")
st.title("Compass Assistance")
st.caption("Travel insurance portfolio dashboard")

path = warehouse.default_path()
if not path.exists():
    st.error(f"No warehouse at {path}. Run `uv run demo reset` first.")
    st.stop()

con = warehouse.connect(path)
try:
    catalogue = metrics.definitions(con).set_index("metric")
    for tab, (_, render) in zip(st.tabs([name for name, _ in TABS]), TABS):
        with tab:
            render(con, catalogue)
finally:
    con.close()
