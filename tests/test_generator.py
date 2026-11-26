"""Generator tests: build the full seeded warehouse and assert through the Metric layer.

These tests may read the generator's configuration, as ADR 0002 allows.
"""

from datetime import date

import pandas as pd
import pytest

from compass import metrics, warehouse
from compass.generator import UNDERWRITING_YEARS, VALUATION_DATE, generate_book, pricing


def test_reset_creates_the_warehouse_from_scratch(full_warehouse):
    con = metrics.connect(full_warehouse)
    by_year = metrics.query(con, ["booking_count", "policy_count"], by=["underwriting_year"]).set_index(
        "underwriting_year")
    con.close()

    assert 45_000 <= by_year.loc[2025, "booking_count"] <= 55_000
    # 2026 is sold only up to the Valuation date (30 September): about three quarters of a year.
    assert 0.6 < by_year.loc[2026, "booking_count"] / by_year.loc[2025, "booking_count"] < 0.85
    assert (by_year.policy_count > by_year.booking_count).all()


def test_two_resets_with_the_same_seed_are_identical(full_warehouse, tmp_path):
    again = warehouse.reset(tmp_path / "again.duckdb", seed=warehouse.DEFAULT_SEED)

    first, second = metrics.connect(full_warehouse), metrics.connect(again)
    for table, key in [("destinations", "destination_id"), ("bookings", "booking_id"),
                       ("policies", "policy_id"), ("claims", "claim_id")]:
        a = first.sql(f"SELECT * FROM {table} ORDER BY {key}").df()
        b = second.sql(f"SELECT * FROM {table} ORDER BY {key}").df()
        assert a.equals(b), table
    first.close()
    second.close()


def test_a_different_seed_gives_a_different_book(full_warehouse, tmp_path):
    other = warehouse.reset(tmp_path / "other.duckdb", seed=7)

    a, b = metrics.connect(full_warehouse), metrics.connect(other)
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
        WHERE underwriting_year = 2025
    """).df().iloc[0]

    assert dates.first_purchase.date() == date(2025, 1, 1)
    assert dates.last_purchase.date() == date(2025, 12, 31)
    # No clumping on 1 January: about one day's worth of the year's purchases.
    assert dates.on_jan_1 < 3 * dates.bookings / 365
    # Late-2025 purchases for early-2026 trips exist.
    assert dates.departing_2026 > 0.02 * dates.bookings
    assert dates.bad_order == 0


def test_underwriting_year_2026_is_purchased_from_1_january_up_to_the_valuation_date(full_con):
    dates = full_con.sql("""
        SELECT min(purchase_date) AS first_purchase, max(purchase_date) AS last_purchase
        FROM metric_policies WHERE underwriting_year = 2026
    """).df().iloc[0]

    assert dates.first_purchase.date() == date(2026, 1, 1)
    assert dates.last_purchase.date() == VALUATION_DATE


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


def test_post_departure_severity_is_lower(full_con):
    # The pricing GLM's post_departure severity coefficient is negative, so post-departure
    # claims are smaller relative to trip cost than cancellations.
    by_type = full_con.sql("""
        SELECT claim_type, avg(paid_amount / trip_cost) AS share_of_trip_cost
        FROM metric_claims GROUP BY 1
    """).df().set_index("claim_type")

    assert by_type.loc["post_departure", "share_of_trip_cost"] < by_type.loc["pre_departure", "share_of_trip_cost"]


@pytest.fixture(scope="module")
def developed_claims(full_warehouse):
    """Every ordinary claim of the seeded book (fully developed), with its Policy's Metric-layer shares."""
    claims = generate_book(warehouse.DEFAULT_SEED, reported_by=None, claims=("ordinary",))["claims"]
    con = metrics.connect(full_warehouse)
    try:
        shares = con.sql(
            "SELECT policy_id, underwriting_year, earned_share, post_departure_share FROM metric_policies").df()
    finally:
        con.close()
    return claims.merge(shares, on="policy_id", validate="many_to_one")


def _within(observed: pd.Series, expected: pd.Series, z: float = 4.0) -> None:
    """The share of claims `observed` (booleans) matches the mean of their probabilities `expected`, within z SE."""
    se = (expected * (1 - expected)).sum() ** 0.5 / len(expected)
    assert abs(observed.mean() - expected.mean()) < z * se, (observed.mean(), expected.mean(), se)


def test_claims_occur_as_premium_is_earned_so_occurred_losses_match_earned_premium(developed_claims):
    # Premium is earned evenly over the cover period (purchase to return), and a claim is as likely on any of
    # its days: the claims that occurred by the Valuation date are each Policy's earned share of its claims.
    # This is what keeps an immature year's A/E unbiased (occurrence never lags earning).
    year = developed_claims[developed_claims.underwriting_year == 2026]
    occurred = year.loss_date <= VALUATION_DATE

    assert 0.3 < occurred.mean() < 0.9  # 2026 is partly earned
    _within(occurred, year.earned_share)


def test_claims_are_post_departure_in_proportion_to_the_trips_days_in_the_cover_period(developed_claims):
    # The Pricing basis splits each Policy's claims by its post_departure_share (trip days / cover days),
    # so Pure premium is the generator's expected loss.
    post = developed_claims.claim_type == "post_departure"

    assert 0.1 < post.mean() < 0.9  # both claim types occur
    _within(post, developed_claims.post_departure_share)


def test_case_reserves_are_zero_so_incurred_equals_paid(full_con):
    totals = metrics.query(full_con, ["paid", "case_reserve", "incurred"]).iloc[0]

    assert totals.case_reserve == 0
    assert totals.incurred == pytest.approx(totals.paid)


# A/E tolerances are statistical: TOLERANCE_SE standard errors of the A/E itself. Claims are compound Poisson, so the
# standard error of a cell's Ultimate is about sqrt(sum of its claims' squared developed amounts); over earned Pure
# premium, that is the A/E's standard error (about 0.03 to 0.06 for a region-year here). 4 SE keeps false failures
# rare across all the cells checked while a misfit of the Drift's size (+40%) still stands out by 7 SE or more.
TOLERANCE_SE = 4.0


def _ae(con, by, year):
    """A/E on Ultimate (`ae`) and on Incurred for one Underwriting year by `by`, with A/E's standard error."""
    frame = metrics.query(con, ["ae", "incurred", "earned_pure_premium"], by=[by],
                          where=f"underwriting_year = {year}").set_index(by)
    frame["ae_on_incurred"] = frame.incurred / frame.earned_pure_premium
    spread = con.sql(f"""
        SELECT c.{by}, sqrt(sum((c.paid_amount * e.amount_factor) ^ 2)) AS ultimate_se
        FROM metric_claims c JOIN metric_experience e USING (policy_id)
        WHERE c.underwriting_year = {year} GROUP BY 1
    """).df().set_index(by)
    frame["se"] = spread.ultimate_se / frame.earned_pure_premium
    return frame


def _about_1(frame, column="ae"):
    off = frame[(frame[column] - 1).abs() >= TOLERANCE_SE * frame.se]
    assert off.empty, off[[column, "se"]]
    assert (frame.se < 0.07).all(), frame.se  # small enough for "about 1" to mean something


def test_2025_ae_is_about_1_across_segments(full_con):
    # The pricing worked in 2025: on Ultimate, with the standard development factors, A/E is about 1.
    by_segment = _ae(full_con, "segment", 2025)

    assert len(by_segment) == 3
    _about_1(by_segment)


@pytest.fixture(scope="module")
def late_claims():
    """Per Underwriting year, the ordinary claims that occurred by the Valuation date but were reported after it.

    From the same seeded book fully developed (every claim reported); the hurricane is left out, since the
    standard factors are not meant to see it.
    """
    every = generate_book(warehouse.DEFAULT_SEED, reported_by=None, claims=("ordinary",))["claims"]
    late = every[(every.loss_date <= VALUATION_DATE) & (every.report_date > VALUATION_DATE)]
    return {year: late[late.claim_id.str.startswith(f"C{year}-")] for year in UNDERWRITING_YEARS}


def _ibnr(con, year):
    return metrics.query(con, ["ibnr_claim_count", "ibnr"], where=f"underwriting_year = {year}").iloc[0]


def test_2025_ibnr_matches_the_claims_that_occurred_but_were_not_reported(full_con, late_claims):
    late, ibnr = late_claims[2025], _ibnr(full_con, 2025)

    assert len(late) > 5  # 2025 is mature: few claims are still unreported
    assert ibnr.ibnr_claim_count == pytest.approx(len(late), rel=0.5)
    assert ibnr.ibnr == pytest.approx(late.paid_amount.sum(), rel=0.5)


def test_2026_ibnr_matches_the_claims_that_occurred_but_were_not_reported(full_con, late_claims):
    # 2026 is immature, so IBNR is material; the standard factors carry no Drift but are level-free,
    # so they still develop the drifted Incurred to about the right amount.
    late, ibnr = late_claims[2026], _ibnr(full_con, 2026)

    assert len(late) > 300
    assert ibnr.ibnr_claim_count == pytest.approx(len(late), rel=0.2)
    assert ibnr.ibnr == pytest.approx(late.paid_amount.sum(), rel=0.2)


def test_2026_drift_is_clear_on_ultimate_for_caribbean_and_gulf_coast_and_partly_hidden_on_incurred(full_con):
    ae = _ae(full_con, "destination_region", 2026)

    for region in ("caribbean", "gulf_coast"):
        assert ae.loc[region, "ae"] > 1.2, region  # "inadequate" on the dashboard's bands
        assert ae.loc[region, "ae"] - 1 > TOLERANCE_SE * ae.loc[region, "se"], region
        assert ae.loc[region, "ae_on_incurred"] < ae.loc[region, "ae"] - 0.1, region
    # The rest of the book is still priced right.
    _about_1(ae.loc[["us_atlantic"]])


def test_2025_ae_is_about_1_by_destination_region(full_con):
    # Before the Drift the pricing worked everywhere, on Ultimate and (2025 being mature) on Incurred.
    ae = _ae(full_con, "destination_region", 2025)

    assert set(ae.index) == {"us_atlantic", "gulf_coast", "caribbean"}
    _about_1(ae)
    _about_1(ae, "ae_on_incurred")


@pytest.fixture(scope="module")
def hurricane_claims():
    """Every claim of the September 2026 Gulf Coast hurricane, reported or not: the seeded book fully developed."""
    return generate_book(warehouse.DEFAULT_SEED, reported_by=None, claims=("hurricane",))["claims"]


def test_the_gulf_coast_hurricane_claims_are_largely_unreported_at_the_valuation_date(full_con, hurricane_claims):
    from compass.generator.truth import HURRICANE

    reported = hurricane_claims[hurricane_claims.report_date <= VALUATION_DATE]

    assert len(hurricane_claims) > 100  # a material event
    assert HURRICANE.landfall.month == 9 and 10 <= HURRICANE.landfall.day <= 20  # mid-September 2026
    assert len(reported) / len(hurricane_claims) < 0.25  # largely unreported at the Valuation date
    assert reported.paid_amount.sum() / hurricane_claims.paid_amount.sum() < 0.25
    # The reported ones are in the warehouse, on Gulf Coast Policies, among the ordinary claims.
    gulf = full_con.sql(f"""
        SELECT policy_id, loss_date, paid_amount FROM metric_claims
        WHERE destination_region = 'gulf_coast' AND loss_date = DATE '{HURRICANE.landfall}'
    """).df()
    merged = reported.merge(gulf, on=["policy_id", "paid_amount"], how="left", indicator=True)
    assert (merged["_merge"] == "both").all()


def test_the_hurricane_loading_covers_the_unreported_event_on_gulf_coast_2026(full_con, hurricane_claims):
    # The loading is an Expert-judgment estimate (calibrated on other seeds), so only roughly right.
    unreported = hurricane_claims[hurricane_claims.report_date > VALUATION_DATE]
    loaded = metrics.query(full_con, ["ultimate", "ultimate_with_loading", "ultimate_claim_count",
                                      "ultimate_claim_count_with_loading"],
                           by=["underwriting_year", "destination_region"]).set_index(
        ["underwriting_year", "destination_region"])

    gulf = loaded.loc[(2026, "gulf_coast")]
    assert gulf.ultimate_with_loading - gulf.ultimate == pytest.approx(unreported.paid_amount.sum(), rel=0.3)
    assert (gulf.ultimate_claim_count_with_loading - gulf.ultimate_claim_count
            == pytest.approx(len(unreported), rel=0.3))
    # Nowhere else: the other regions and 2025 (all returned by the event) carry no loading.
    others = loaded.drop(index=(2026, "gulf_coast"))
    assert list(others.ultimate_with_loading) == pytest.approx(list(others.ultimate))
