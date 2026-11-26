"""Seam 2: the Legacy dashboard, run with Streamlit's app test harness on a built warehouse."""

from importlib import resources

import pytest
from streamlit.testing.v1 import AppTest

from compass import metrics, warehouse

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


def test_there_is_no_geographic_ae_view(app):
    labels = [tab.label for tab in app.tabs] + [h.value for h in app.subheader] + [h.value for h in app.header]
    assert not any("A/E" in label and ("region" in label.lower() or "destination" in label.lower())
                   for label in labels)
