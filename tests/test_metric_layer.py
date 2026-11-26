"""Seam 1: the Metric layer over a tiny hand-built book.

Every expected value below is computed by hand from the rows in `tiny_book`.
"""

import pytest

from compass import metrics


def test_hotel_and_flight_booking_counts_once_but_holds_two_policies(tiny_book):
    result = metrics.query(tiny_book, ["booking_count", "policy_count"])

    # B1 hotel_and_flight (2 policies), B2 hotel_only, B3 flight_only
    assert result.loc[0, "booking_count"] == 3
    assert result.loc[0, "policy_count"] == 4


def test_written_premium_on_both_bases(tiny_book):
    result = metrics.query(tiny_book, ["written_pure_premium", "written_commercial_premium"])

    assert result.loc[0, "written_pure_premium"] == pytest.approx(160.00)  # 100 + 20 + 10 + 30
    assert result.loc[0, "written_commercial_premium"] == pytest.approx(177.60)  # 111 + 22.2 + 11.1 + 33.3


def test_by_product_a_hotel_and_flight_booking_counts_under_both_products(tiny_book):
    result = metrics.query(
        tiny_book, ["booking_count", "policy_count", "written_pure_premium"], by=["product"]
    ).set_index("product")

    assert result.loc["hotel", "booking_count"] == 2  # B1, B2
    assert result.loc["flight", "booking_count"] == 2  # B1, B3
    assert result.loc["hotel", "policy_count"] == 2
    assert result.loc["flight", "policy_count"] == 2
    assert result.loc["hotel", "written_pure_premium"] == pytest.approx(110.00)
    assert result.loc["flight", "written_pure_premium"] == pytest.approx(50.00)


def test_breakdown_by_segment_region_and_departure_month(tiny_book):
    result = metrics.query(
        tiny_book,
        ["booking_count", "written_commercial_premium"],
        by=["segment", "destination_region", "departure_month"],
    )

    rows = {
        (r.segment, r.destination_region, r.departure_month): (r.booking_count, r.written_commercial_premium)
        for r in result.itertuples()
    }
    assert rows.keys() == {
        ("winter_birds", "us_atlantic", 2),
        ("baseline", "gulf_coast", 7),
        ("holiday_travelers", "caribbean", 1),
    }
    assert rows[("winter_birds", "us_atlantic", 2)] == (1, pytest.approx(133.20))


def test_filter_restricts_every_metric(tiny_book):
    result = metrics.query(
        tiny_book, ["booking_count", "policy_count"], where="coverage_type = 'hotel_and_flight'"
    )

    assert result.loc[0, "booking_count"] == 1
    assert result.loc[0, "policy_count"] == 2


def test_every_metric_in_the_catalogue_is_documented(tiny_book):
    catalogue = metrics.definitions(tiny_book)

    assert set(catalogue.metric) >= {
        "booking_count", "policy_count", "written_pure_premium", "written_commercial_premium"
    }
    assert catalogue.description.str.len().min() > 20
