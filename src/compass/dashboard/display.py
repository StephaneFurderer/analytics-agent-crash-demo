"""Display helpers: formatting only. No metric is computed here."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def format_value(value: float, unit: str) -> str:
    if pd.isna(value):  # e.g. a breakdown cell with no claims
        return "–"
    if unit == "count":
        return f"{value:,.0f}"
    if unit == "currency":
        return f"${value:,.0f}"
    return f"{value:.3f}"


def tiles(row: pd.Series, catalogue: pd.DataFrame) -> None:
    """One st.metric tile per metric in `row`, labelled from the catalogue."""
    for column, metric in zip(st.columns(len(row)), row.index):
        column.metric(catalogue.loc[metric, "label"], format_value(row[metric], catalogue.loc[metric, "unit"]),
                      help=catalogue.loc[metric, "description"])


def table(frame: pd.DataFrame, catalogue: pd.DataFrame) -> None:
    """A metric breakdown with catalogue labels as column headers."""
    shown = frame.copy()
    for metric in [c for c in frame.columns if c in catalogue.index]:
        shown[metric] = [format_value(v, catalogue.loc[metric, "unit"]) for v in frame[metric]]
    labels = {c: catalogue.loc[c, "label"] if c in catalogue.index
              else c.replace("_", " ").capitalize() if c.islower() else c  # a snake_case dim, or a ready label
              for c in frame.columns}
    st.dataframe(shown.rename(columns=labels), hide_index=True, use_container_width=True)
