"""Seam 2: the Legacy dashboard, run with Streamlit's app test harness on a built warehouse."""

from importlib import resources

import pytest
from streamlit.testing.v1 import AppTest

from compass import metrics, warehouse
from compass.generator import pricing

APP = str(resources.files("compass.dashboard").joinpath("app.py"))


@pytest.fixture
def app(full_warehouse, monkeypatch):
    monkeypatch.setenv(warehouse.PATH_ENV, str(full_warehouse))
    return AppTest.from_file(APP, default_timeout=30).run()


def test_portfolio_tab_renders_without_exceptions(app):
    assert not app.exception
    assert "Portfolio" in [tab.label for tab in app.tabs]


def test_portfolio_tab_shows_metric_layer_numbers(app, full_con):
    expected = metrics.query(full_con, ["booking_count", "policy_count"]).iloc[0]
    shown = {m.label: m.value for m in app.metric}

    assert shown["Bookings"] == f"{expected.booking_count:,.0f}"
    assert shown["Policies"] == f"{expected.policy_count:,.0f}"


def test_pricing_tab_renders_without_exceptions(app):
    assert not app.exception
    assert "Pricing" in [tab.label for tab in app.tabs]


def test_pricing_tab_shows_the_generators_coefficients_exactly(app):
    shown = [frame.value for frame in app.dataframe if "Coefficient" in frame.value.columns]
    tables = [dict(zip(frame.Term, frame.Coefficient)) for frame in shown]

    assert dict(pricing.PRICING_GLM_2025.frequency) in tables
    assert dict(pricing.PRICING_GLM_2025.severity) in tables


def test_pricing_tab_shows_expected_values_by_segment(app, full_con):
    expected = metrics.query(full_con, ["expected_claim_count"], by=["segment"])
    shown = [frame.value for frame in app.dataframe if "Expected claims" in frame.value.columns]

    assert len(shown) == 1
    assert list(shown[0].Segment) == list(expected.segment)
    assert list(shown[0]["Expected claims"]) == [f"{v:,.0f}" for v in expected.expected_claim_count]


def test_there_is_no_geographic_ae_view(app):
    labels = [tab.label for tab in app.tabs] + [h.value for h in app.subheader] + [h.value for h in app.header]
    assert not any("A/E" in label and ("region" in label.lower() or "destination" in label.lower())
                   for label in labels)
