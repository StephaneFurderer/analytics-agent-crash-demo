"""Display helpers: formatting only. No metric is computed here."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics


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
        d = metrics.definition(catalogue, metric)
        column.metric(d.label, format_value(row[metric], d.unit), help=d.description)


def table(frame: pd.DataFrame, catalogue: pd.DataFrame) -> None:
    """A metric breakdown with catalogue labels as column headers."""
    shown = frame.copy()
    for metric in [c for c in frame.columns if c in catalogue.index]:
        unit = metrics.definition(catalogue, metric).unit
        shown[metric] = [format_value(v, unit) for v in frame[metric]]
    labels = {c: metrics.definition(catalogue, c).label if c in catalogue.index
              else c.replace("_", " ").capitalize() if c.islower() else c  # a snake_case dim, or a ready label
              for c in frame.columns}
    st.dataframe(shown.rename(columns=labels), hide_index=True, use_container_width=True)
