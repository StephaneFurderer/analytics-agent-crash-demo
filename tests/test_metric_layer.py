"""Seam 1: the Metric layer over a tiny hand-built book.

Every expected value below is computed by hand from the rows in `tiny_book`.
"""

import pytest

from compass import metrics


def test_hotel_and_flight_booking_counts_once_but_holds_two_policies(tiny_book):
    result = metrics.query(tiny_book, ["booking_count", "policy_count"])

    # B1 hotel_and_flight (2 policies), B2 hotel_only, B3 flight_only, B4 hotel_only
    assert result.loc[0, "booking_count"] == 4
    assert result.loc[0, "policy_count"] == 5


def test_written_premium_on_both_bases(tiny_book):
    result = metrics.query(tiny_book, ["written_pure_premium", "written_commercial_premium"])

    assert result.loc[0, "written_pure_premium"] == pytest.approx(200.00)  # 100 + 20 + 10 + 30 + 40
    assert result.loc[0, "written_commercial_premium"] == pytest.approx(222.00)  # 111 + 22.2 + 11.1 + 33.3 + 44.4


def test_by_product_a_hotel_and_flight_booking_counts_under_both_products(tiny_book):
    result = metrics.query(
        tiny_book, ["booking_count", "policy_count", "written_pure_premium"], by=["product"]
    ).set_index("product")

    assert result.loc["hotel", "booking_count"] == 3  # B1, B2, B4
    assert result.loc["flight", "booking_count"] == 2  # B1, B3
    assert result.loc["hotel", "policy_count"] == 3
    assert result.loc["flight", "policy_count"] == 2
    assert result.loc["hotel", "written_pure_premium"] == pytest.approx(150.00)
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
        ("baseline", "us_atlantic", 9),
    }
    assert rows[("winter_birds", "us_atlantic", 2)] == (1, pytest.approx(133.20))


def test_filter_restricts_every_metric(tiny_book):
    result = metrics.query(
        tiny_book, ["booking_count", "policy_count"], where="coverage_type = 'hotel_and_flight'"
    )

    assert result.loc[0, "booking_count"] == 1
    assert result.loc[0, "policy_count"] == 2


def test_earned_premium_is_prorated_at_the_valuation_date_on_both_bases(tiny_book):
    result = metrics.query(tiny_book, ["earned_pure_premium", "earned_commercial_premium"])

    # B1, B2 and B3 have returned by 2026-09-30: fully earned (160 pure, 177.6 commercial).
    # B4 is 20 days into its 40 days from purchase to return: half earned (20 pure, 22.2 commercial).
    assert result.loc[0, "earned_pure_premium"] == pytest.approx(180.00)
    assert result.loc[0, "earned_commercial_premium"] == pytest.approx(199.80)


def test_underwriting_year_is_the_year_of_purchase_not_departure(tiny_book):
    result = metrics.query(
        tiny_book, ["booking_count", "written_pure_premium", "earned_pure_premium"], by=["underwriting_year"]
    ).set_index("underwriting_year")

    # B3 departs in 2026 but was purchased in November 2025: it belongs to 2025.
    assert list(result.index) == [2025, 2026]
    assert result.loc[2025, "booking_count"] == 3  # B1, B2, B3
    assert result.loc[2025, "written_pure_premium"] == pytest.approx(160.00)
    assert result.loc[2026, "booking_count"] == 1  # B4
    assert result.loc[2026, "earned_pure_premium"] == pytest.approx(20.00)


def test_reported_count_paid_case_reserve_and_incurred(tiny_book):
    result = metrics.query(tiny_book, ["reported_claim_count", "paid", "case_reserve", "incurred"])

    assert result.loc[0, "reported_claim_count"] == 3  # C1, C2, C3
    assert result.loc[0, "paid"] == pytest.approx(4550.00)  # 4000 + 250 + 300
    assert result.loc[0, "case_reserve"] == pytest.approx(0.0)
    assert result.loc[0, "incurred"] == pytest.approx(4550.00)  # Paid + Case reserve


def test_claims_break_down_alongside_premium(tiny_book):
    result = metrics.query(
        tiny_book, ["policy_count", "reported_claim_count", "incurred"], by=["product", "underwriting_year"]
    )

    rows = {(r.product, r.underwriting_year): (r.policy_count, r.reported_claim_count, r.incurred)
            for r in result.fillna(0).itertuples()}
    assert rows[("hotel", 2025)] == (2, 2, pytest.approx(4300.00))  # B1-H, B2-H; C1, C3
    assert rows[("flight", 2025)] == (2, 1, pytest.approx(250.00))  # B1-F, B3-F; C2
    assert rows[("hotel", 2026)] == (1, 0, 0)  # B4-H, no claims


def test_every_metric_in_the_catalogue_is_documented(tiny_book):
    catalogue = metrics.definitions(tiny_book)

    assert set(catalogue.metric) >= {
        "booking_count", "policy_count", "written_pure_premium", "written_commercial_premium",
        "earned_pure_premium", "earned_commercial_premium",
        "reported_claim_count", "paid", "case_reserve", "incurred",
    }
    assert catalogue.description.str.len().min() > 20
