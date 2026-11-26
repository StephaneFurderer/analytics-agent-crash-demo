"""Seam 1: exposure and the hurricane loading in the Metric layer, over the tiny hand-built book.

A Policy is at risk on a date from its purchase date to its return date, both included. Tiny book:
B1 (Miami, 10 Jan - 3 Mar 2025, two Policies 9000 + 600), B2-H (Galveston, 1 Jun - 4 Jul 2025, 500),
B3-F (Nassau, 20 Nov 2025 - 12 Jan 2026, 800), B4-H (Miami, 10 Sep - 20 Oct 2026, 7000).
"""

from datetime import date

import pytest

from compass import metrics


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
