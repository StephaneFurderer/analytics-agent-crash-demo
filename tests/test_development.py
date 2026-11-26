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
