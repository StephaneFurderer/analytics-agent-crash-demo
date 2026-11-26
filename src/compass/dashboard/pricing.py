"""Pricing tab: the Pricing basis (the pricing GLM) and its expected values."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from compass import metrics
from compass.dashboard import display

EXPECTED = ["policy_count", "expected_claim_count", "expected_claim_frequency", "expected_average_severity",
            "written_pure_premium", "written_commercial_premium"]


def render(con, catalogue: pd.DataFrame) -> None:
    basis = metrics.pricing_basis(con)
    st.header("Pricing")
    st.caption(f"The Pricing basis: {', '.join(basis.model.unique())}, as the pricing team set it.")

    left, right = st.columns(2)
    for column, component, title in [(left, "frequency", "Frequency (Poisson, log link)"),
                                     (right, "severity", "Severity (Gamma, log link)")]:
        with column:
            st.subheader(title)
            _coefficients(basis[basis.component == component])

    st.subheader("Premium")
    _coefficients(basis[basis.component == "premium"])

    st.subheader("Expected values by segment")
    display.table(metrics.query(con, EXPECTED, by=["segment"]), catalogue)


def _coefficients(rows: pd.DataFrame) -> None:
    shown = rows[["term", "coefficient"]].rename(columns={"term": "Term", "coefficient": "Coefficient"})
    st.dataframe(shown, hide_index=True, use_container_width=True)
