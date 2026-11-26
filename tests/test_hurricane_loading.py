"""Seam 1: exposure and the hurricane loading in the Metric layer, over the tiny hand-built book.

A Policy is at risk on a date from its purchase date to its return date, both included. Tiny book:
B1 (Miami, 10 Jan - 3 Mar 2025, two Policies 9000 + 600), B2-H (Galveston, 1 Jun - 4 Jul 2025, 500),
B3-F (Nassau, 20 Nov 2025 - 12 Jan 2026, 800), B4-H (Miami, 10 Sep - 20 Oct 2026, 7000).
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import compass
from compass import metrics, warehouse
from conftest import BOOKINGS, CLAIMS, DESTINATIONS, DEVELOPMENT_FACTORS, POLICIES, PRICING_COEFFICIENTS


@pytest.mark.parametrize("on, expected", [
    (date(2025, 1, 20), 9600.0),  # B1-H and B1-F
    (date(2025, 7, 4), 500.0),  # B2-H, on its return date
    (date(2025, 7, 5), 0.0),  # B2 is back
    (date(2026, 1, 1), 800.0),  # B3-F
    (date(2026, 9, 16), 7000.0),  # B4-H
])
def test_exposure_is_trip_cost_at_risk_on_a_date(tiny_book, on, expected):
    result = metrics.exposure(tiny_book, on)

    assert result.loc[0, "exposure"] == pytest.approx(expected)


def test_exposure_breaks_down_like_any_metric(tiny_book):
    result = metrics.exposure(tiny_book, date(2025, 1, 20), by=["product"]).set_index("product")

    assert result.loc["hotel", "exposure"] == pytest.approx(9000.0)
    assert result.loc["flight", "exposure"] == pytest.approx(600.0)
    assert result.loc["hotel", "policies_at_risk"] == 1


def test_exposure_can_be_filtered(tiny_book):
    result = metrics.exposure(tiny_book, date(2025, 1, 20), where="product = 'flight'")

    assert result.loc[0, "exposure"] == pytest.approx(600.0)
    assert result.loc[0, "policies_at_risk"] == 1


# The tiny book's loading (conftest.HURRICANE_LOADING): a made-up Gulf Coast storm on 2 July 2025, loading
# 0.5 claims per Policy at risk and 0.4 of trip cost at risk. Only B2-H (Galveston, 500) is at risk then:
# 0.5 claims and 200 on Underwriting year 2025. Ultimate without the loading: 4610 (2025), 0 (2026).

def test_the_hurricane_loading_is_expected_event_claims_on_the_policies_at_risk(tiny_book):
    result = metrics.query(tiny_book, ["hurricane_loading_claim_count", "hurricane_loading"],
                           by=["destination_region"]).set_index("destination_region")

    assert result.loc["gulf_coast", "hurricane_loading_claim_count"] == pytest.approx(0.5)
    assert result.loc["gulf_coast", "hurricane_loading"] == pytest.approx(200.0)
    assert result.loc[["us_atlantic", "caribbean"], "hurricane_loading"].sum() == 0


def test_ultimate_with_and_without_the_hurricane_loading(tiny_book):
    result = metrics.query(
        tiny_book, ["ultimate", "ultimate_with_loading", "ultimate_claim_count", "ultimate_claim_count_with_loading"],
        by=["underwriting_year"]).set_index("underwriting_year")

    assert result.loc[2025, "ultimate"] == pytest.approx(4610.0)  # the default: no loading
    assert result.loc[2025, "ultimate_with_loading"] == pytest.approx(4810.0)
    assert result.loc[2025, "ultimate_claim_count"] == pytest.approx(3.1)
    assert result.loc[2025, "ultimate_claim_count_with_loading"] == pytest.approx(3.6)
    assert result.loc[2026, "ultimate_with_loading"] == pytest.approx(0.0)


def test_ae_and_loss_ratio_with_the_hurricane_loading(tiny_book):
    result = metrics.query(tiny_book, ["ae", "ae_with_loading", "loss_ratio_with_loading"]).iloc[0]

    assert result.ae == pytest.approx(4610.0 / 180.0)  # the default: no loading
    assert result.ae_with_loading == pytest.approx(4810.0 / 180.0)  # over earned Pure premium
    assert result.loss_ratio_with_loading == pytest.approx(4810.0 / 199.8)  # over earned Commercial premium


def test_the_warehouse_reads_the_version_controlled_hurricane_loading_file(full_con):
    assumptions = Path(compass.__file__).parent / "assumptions"
    on_file = pd.read_csv(assumptions / "hurricane_loading.csv", comment="#", parse_dates=["event_date"])

    in_use = metrics.hurricane_loading(full_con)

    pd.testing.assert_frame_equal(in_use, on_file, check_dtype=False)
    assert list(on_file.destination_region) == ["gulf_coast"]
    # Kept apart from the standard development factors.
    assert "hurricane" not in (assumptions / "development_factors.csv").read_text().lower()


def test_editing_the_hurricane_loading_changes_ultimate_with_loading(tmp_path):
    edited = [{"event": "edited storm", "destination_region": "us_atlantic", "event_date": date(2026, 9, 16),
               "count_per_policy": 0.1, "amount_per_trip_cost": 0.2}]
    built = warehouse.write(tmp_path / "edited.duckdb", destinations=DESTINATIONS, bookings=BOOKINGS,
                            policies=POLICIES, claims=CLAIMS, pricing_coefficients=PRICING_COEFFICIENTS)
    con = metrics.connect(built, development_factors=DEVELOPMENT_FACTORS, hurricane_loading=edited)
    try:
        result = metrics.query(con, ["ultimate", "ultimate_with_loading", "ultimate_claim_count_with_loading"],
                               by=["underwriting_year"]).set_index("underwriting_year")
    finally:
        con.close()

    assert result.loc[2026, "ultimate"] == pytest.approx(0.0)
    assert result.loc[2026, "ultimate_with_loading"] == pytest.approx(1400.0)  # B4-H: 7000 at risk x 0.2
    assert result.loc[2026, "ultimate_claim_count_with_loading"] == pytest.approx(0.1)
    assert result.loc[2025, "ultimate_with_loading"] == pytest.approx(4610.0)  # no loading on 2025 now
