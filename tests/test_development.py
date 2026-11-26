"""Seam 1: Development, Ultimate and A/E in the Metric layer, over the tiny hand-built book.

The tiny book's claims: C1 4000 on B1-H and C2 250 on B1-F (maturity 19, factors 1.0 / 1.0),
C3 300 on B2-H (maturity 14, factors 1.1 count / 1.2 amount). B3 (maturity 8) and B4 (maturity 0)
have no reported claims, so chain-ladder development adds nothing for them.
"""

from pathlib import Path

import pandas as pd
import pytest

import compass
from compass import metrics, warehouse
from conftest import BOOKINGS, CLAIMS, DESTINATIONS, POLICIES, PRICING_COEFFICIENTS


def test_ibnr_count_and_amount_come_from_the_factors_at_each_maturity(tiny_book):
    result = metrics.query(tiny_book, ["ibnr_claim_count", "ibnr"])

    assert result.loc[0, "ibnr_claim_count"] == pytest.approx(0.1)  # 1 claim on B2 x (1.1 - 1)
    assert result.loc[0, "ibnr"] == pytest.approx(60.0)  # 300 on B2 x (1.2 - 1)


def test_ultimate_is_incurred_plus_ibnr_per_underwriting_year(tiny_book):
    result = metrics.query(
        tiny_book, ["incurred", "ibnr", "ultimate", "ultimate_claim_count"], by=["underwriting_year"]
    ).set_index("underwriting_year")

    assert result.loc[2025, "ultimate"] == pytest.approx(4610.0)  # 4550 Incurred + 60 IBNR
    assert result.loc[2025, "ultimate_claim_count"] == pytest.approx(3.1)  # 3 reported + 0.1 IBNR
    assert result.loc[2026, "ultimate"] == pytest.approx(0.0)  # B4: no claims reported, nothing to develop
    assert result.loc[2026, "ultimate_claim_count"] == pytest.approx(0.0)


def test_frequency_severity_loss_ratio_and_ae_on_ultimate(tiny_book):
    result = metrics.query(tiny_book, ["ultimate_frequency", "ultimate_severity", "loss_ratio", "ae"])

    # Earned Policies: B1-H, B1-F, B2-H, B3-F fully earned, B4-H half earned = 4.5
    assert result.loc[0, "ultimate_frequency"] == pytest.approx(3.1 / 4.5)
    assert result.loc[0, "ultimate_severity"] == pytest.approx(4610.0 / 3.1)
    assert result.loc[0, "loss_ratio"] == pytest.approx(4610.0 / 199.8)  # over earned Commercial premium
    assert result.loc[0, "ae"] == pytest.approx(4610.0 / 180.0)  # over earned Pure premium


def test_ae_by_underwriting_year_uses_that_years_earned_pure_premium(tiny_book):
    result = metrics.query(tiny_book, ["ae"], by=["underwriting_year"]).set_index("underwriting_year")

    assert result.loc[2025, "ae"] == pytest.approx(4610.0 / 160.0)
    assert result.loc[2026, "ae"] == pytest.approx(0.0)


@pytest.mark.parametrize("ae, band", [
    (0.80, "adequate"), (1.05, "adequate"), (1.0501, "watch"), (1.20, "watch"), (1.2001, "inadequate"),
    (25.6, "inadequate"),
])
def test_ae_bands(tiny_book, ae, band):
    assert metrics.ae_band(tiny_book, ae) == band


def test_ae_bands_are_defined_once_as_data(tiny_book):
    bands = metrics.ae_bands(tiny_book)

    assert list(bands.band) == ["adequate", "watch", "inadequate"]
    assert list(bands.upper_bound[:2]) == [1.05, 1.20]


def test_the_warehouse_reads_the_version_controlled_factors_file(full_con):
    csv = Path(compass.__file__).parent / "assumptions" / "development_factors.csv"
    on_file = pd.read_csv(csv, comment="#")

    in_use = metrics.development_factors(full_con)

    pd.testing.assert_frame_equal(in_use, on_file, check_dtype=False)


def test_editing_the_factors_changes_ibnr(tmp_path):
    edited = [{"maturity_months": 0, "count_factor": 3.0, "amount_factor": 3.0}]
    built = warehouse.write(tmp_path / "edited.duckdb", destinations=DESTINATIONS, bookings=BOOKINGS,
                            policies=POLICIES, claims=CLAIMS, pricing_coefficients=PRICING_COEFFICIENTS,
                            development_factors=edited)
    con = warehouse.connect(built)
    try:
        assert metrics.query(con, ["ibnr"]).loc[0, "ibnr"] == pytest.approx(2 * 4550.0)
    finally:
        con.close()
