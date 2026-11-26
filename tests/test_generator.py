"""Generator tests: build the full seeded warehouse and assert through the Metric layer.

These tests may read the generator's configuration, as ADR 0002 allows.
"""

from datetime import date

import pytest

from compass import metrics, warehouse
from compass.generator import VALUATION_DATE, pricing


def test_reset_creates_the_warehouse_from_scratch(full_warehouse):
    con = warehouse.connect(full_warehouse)
    total = metrics.query(con, ["booking_count", "policy_count"])
    con.close()

    assert 45_000 <= total.loc[0, "booking_count"] <= 55_000
    assert total.loc[0, "policy_count"] > total.loc[0, "booking_count"]


def test_two_resets_with_the_same_seed_are_identical(full_warehouse, tmp_path):
    again = warehouse.reset(tmp_path / "again.duckdb", seed=warehouse.DEFAULT_SEED)

    first, second = warehouse.connect(full_warehouse), warehouse.connect(again)
    for table, key in [("destinations", "destination_id"), ("bookings", "booking_id"),
                       ("policies", "policy_id"), ("claims", "claim_id")]:
        a = first.sql(f"SELECT * FROM {table} ORDER BY {key}").df()
        b = second.sql(f"SELECT * FROM {table} ORDER BY {key}").df()
        assert a.equals(b), table
    first.close()
    second.close()


def test_a_different_seed_gives_a_different_book(full_warehouse, tmp_path):
    other = warehouse.reset(tmp_path / "other.duckdb", seed=7)

    a, b = warehouse.connect(full_warehouse), warehouse.connect(other)
    premium_a = metrics.query(a, ["written_pure_premium"]).loc[0, "written_pure_premium"]
    premium_b = metrics.query(b, ["written_pure_premium"]).loc[0, "written_pure_premium"]
    a.close()
    b.close()
    assert premium_a != premium_b


def test_book_has_three_segments_and_38_destinations_in_three_regions(full_con):
    by_segment = metrics.query(full_con, ["booking_count"], by=["segment"])
    destinations = full_con.sql(
        "SELECT destination_region, count(DISTINCT destination) AS n FROM metric_policies GROUP BY 1"
    ).df()

    assert set(by_segment.segment) == {"winter_birds", "holiday_travelers", "baseline"}
    assert destinations.n.sum() == 38
    assert set(destinations.destination_region) == {"us_atlantic", "gulf_coast", "caribbean"}


def test_hotel_and_flight_bookings_produce_two_policies(full_con):
    by_coverage = metrics.query(
        full_con, ["booking_count", "policy_count"], by=["coverage_type"]
    ).set_index("coverage_type")

    hf = by_coverage.loc["hotel_and_flight"]
    assert hf.policy_count == 2 * hf.booking_count
    for single in ("hotel_only", "flight_only"):
        assert by_coverage.loc[single, "policy_count"] == by_coverage.loc[single, "booking_count"]


def test_purchase_dates_are_natural_within_underwriting_year_2025(full_con):
    dates = full_con.sql("""
        SELECT min(purchase_date) AS first_purchase,
               max(purchase_date) AS last_purchase,
               count(DISTINCT booking_id) FILTER (WHERE purchase_date = DATE '2025-01-01') AS on_jan_1,
               count(DISTINCT booking_id) AS bookings,
               count(DISTINCT booking_id) FILTER (WHERE departure_date >= DATE '2026-01-01') AS departing_2026,
               count(*) FILTER (NOT (purchase_date < departure_date AND departure_date < return_date)) AS bad_order
        FROM metric_policies
    """).df().iloc[0]

    assert dates.first_purchase.date() == date(2025, 1, 1)
    assert dates.last_purchase.date() == date(2025, 12, 31)
    # No clumping on 1 January: about one day's worth of the year's purchases.
    assert dates.on_jan_1 < 3 * dates.bookings / 365
    # Late-2025 purchases for early-2026 trips exist.
    assert dates.departing_2026 > 0.02 * dates.bookings
    assert dates.bad_order == 0


def test_commercial_premium_is_pure_premium_plus_the_pricing_expense_load(full_con):
    totals = metrics.query(full_con, ["written_pure_premium", "written_commercial_premium"])

    ratio = totals.loc[0, "written_commercial_premium"] / totals.loc[0, "written_pure_premium"]
    assert ratio == pytest.approx(pricing.PRICING_GLM_2025.expense_load, abs=1e-3)


def test_premium_is_positive_on_every_policy(full_con):
    assert full_con.sql(
        "SELECT count(*) FROM metric_policies WHERE pure_premium <= 0 OR trip_cost <= 0"
    ).fetchall()[0][0] == 0


def test_underwriting_year_2025_has_claims_and_none_exceeds_trip_cost(full_con):
    claims = metrics.query(full_con, ["reported_claim_count", "incurred"], by=["underwriting_year"])
    over_cap = full_con.sql(
        "SELECT count(*) FROM metric_claims WHERE paid_amount > trip_cost OR paid_amount <= 0"
    ).fetchall()[0][0]

    assert claims.loc[claims.underwriting_year == 2025, "reported_claim_count"].item() > 1_000
    assert over_cap == 0


def test_claims_are_dated_on_the_trip_timeline(full_con):
    misdated = full_con.sql("""
        SELECT
            count(*) FILTER (WHERE claim_type = 'post_departure'
                             AND NOT (loss_date BETWEEN departure_date AND return_date)) AS post_outside_trip,
            count(*) FILTER (WHERE claim_type = 'pre_departure'
                             AND NOT (loss_date >= purchase_date AND loss_date < departure_date)) AS pre_outside,
            count(*) FILTER (WHERE report_date < loss_date) AS reported_before_loss
        FROM metric_claims
    """).df().iloc[0]

    assert misdated.post_outside_trip == 0
    assert misdated.pre_outside == 0
    assert misdated.reported_before_loss == 0


def test_no_claim_is_reported_after_the_valuation_date(full_con):
    last_report = full_con.sql("SELECT max(report_date) FROM metric_claims").fetchall()[0][0]
    valuation = full_con.sql("SELECT valuation_date()").fetchall()[0][0]

    assert valuation == VALUATION_DATE
    assert last_report <= VALUATION_DATE


def test_both_claim_types_occur_and_post_departure_severity_is_lower(full_con):
    # The pricing GLM's post_departure severity coefficient is negative, so post-departure
    # claims are smaller relative to trip cost than cancellations.
    by_type = full_con.sql("""
        SELECT claim_type, count(*) AS n, avg(paid_amount / trip_cost) AS share_of_trip_cost
        FROM metric_claims GROUP BY 1
    """).df().set_index("claim_type")
    share = pricing.PRICING_GLM_2025.post_departure_share
    n = by_type.n.sum()

    assert by_type.loc["post_departure", "n"] / n == pytest.approx(share, abs=0.05)
    assert by_type.loc["post_departure", "share_of_trip_cost"] < by_type.loc["pre_departure", "share_of_trip_cost"]


def test_case_reserves_are_zero_so_incurred_equals_paid(full_con):
    totals = metrics.query(full_con, ["paid", "case_reserve", "incurred"]).iloc[0]

    assert totals.case_reserve == 0
    assert totals.incurred == pytest.approx(totals.paid)
