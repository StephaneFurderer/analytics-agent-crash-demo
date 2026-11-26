"""Seam 1: Development, Ultimate and A/E in the Metric layer, over the tiny hand-built book.

The tiny book's claims: C1 4000 on B1-H and C2 250 on B1-F (maturity 19, factors 1.0 / 1.0),
C3 300 on B2-H (maturity 14, factors 1.1 count / 1.2 amount). B3 (maturity 8) and B4 (maturity 0)
have no reported claims, so chain-ladder development adds nothing for them.
"""

import pytest

from compass import metrics


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
