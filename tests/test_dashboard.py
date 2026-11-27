"""Seam 2: the Legacy dashboard, run with Streamlit's app test harness on a built warehouse."""

import json
from importlib import resources

import pytest
from streamlit.testing.v1 import AppTest

from compass import metrics, warehouse
from compass.dashboard import performance
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


def test_portfolio_tab_shows_incurred_claims_and_earned_premium(app, full_con):
    expected = metrics.query(
        full_con, ["earned_pure_premium", "earned_commercial_premium", "reported_claim_count", "incurred"]
    ).iloc[0]
    shown = {m.label: m.value for m in app.metric}

    assert shown["Earned pure premium"] == f"${expected.earned_pure_premium:,.0f}"
    assert shown["Earned commercial premium"] == f"${expected.earned_commercial_premium:,.0f}"
    assert shown["Reported claims"] == f"{expected.reported_claim_count:,.0f}"
    assert shown["Incurred"] == f"${expected.incurred:,.0f}"


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
    ae_tables = [frame.value for frame in app.dataframe if "A/E" in frame.value.columns]
    assert ae_tables
    assert not any(col in frame.columns for frame in ae_tables for col in ("Destination region", "Destination"))


def test_performance_tab_renders_without_exceptions(app):
    assert not app.exception
    assert [tab.label for tab in app.tabs][-1] == "Performance"


def _ae_table(app, column):
    shown = [frame.value for frame in app.dataframe if column in frame.value.columns and "A/E" in frame.value]
    assert len(shown) == 1
    return shown[0]


def test_performance_tab_shows_ae_and_band_by_segment_for_the_latest_underwriting_year(app, full_con):
    # One Underwriting year at a time, so 2026's Drift isn't diluted by mature 2025.
    expected = metrics.query(full_con, ["ae"], by=["segment"], where="underwriting_year = 2026")
    shown = _ae_table(app, "Segment")

    assert app.selectbox(key=performance.YEAR_KEY).value == 2026
    assert list(shown.Segment) == list(expected.segment)
    assert list(shown["A/E"]) == [f"{v:.3f}" for v in expected.ae]
    assert list(shown["A/E band"]) == [metrics.ae_band(full_con, v) for v in expected.ae]


def test_performance_tab_shows_ae_by_departure_month_for_the_chosen_underwriting_year(app, full_con):
    app.selectbox(key=performance.YEAR_KEY).set_value(2025).run()
    expected = metrics.query(full_con, ["ae"], by=["departure_month"], where="underwriting_year = 2025")
    shown = _ae_table(app, "Departure month")

    assert list(shown["A/E"]) == [f"{v:.3f}" for v in expected.ae]
    segments = metrics.query(full_con, ["ae"], by=["segment"], where="underwriting_year = 2025")
    assert list(_ae_table(app, "Segment")["A/E"]) == [f"{v:.3f}" for v in segments.ae]


def test_portfolio_tab_charts_bookings_by_departure_month_per_underwriting_year(app):
    [heading] = [h.value for h in app.subheader if h.value.startswith("Bookings by departure month")]
    [chart] = app.get("vega_lite_chart")
    spec = json.loads(chart.proto.spec)

    assert "underwriting year" in heading.lower()
    assert "color" in spec["encoding"]  # one series per Underwriting year


def test_performance_tab_shows_ultimate_and_ae_tiles(app, full_con):
    expected = metrics.query(full_con, ["ultimate", "ae"]).iloc[0]
    shown = {m.label: m.value for m in app.metric}

    assert shown["Ultimate"] == f"${expected.ultimate:,.0f}"
    assert shown["A/E"] == f"{expected.ae:.3f}"


def test_performance_tab_shows_2026_ae_above_1_by_underwriting_year(app):
    # The Drift is visible in aggregate, but the dashboard can't say where it comes from.
    shown = [frame.value for frame in app.dataframe
             if "Underwriting year" in frame.value.columns and "A/E band" in frame.value.columns]

    assert len(shown) == 1
    by_year = shown[0].set_index(shown[0]["Underwriting year"].astype(str).str.replace(",", ""))
    assert float(by_year.loc["2025", "A/E"]) == pytest.approx(1.0, abs=0.05)
    assert float(by_year.loc["2026", "A/E"]) > 1.15
    assert by_year.loc["2026", "A/E band"] != by_year.loc["2025", "A/E band"]
