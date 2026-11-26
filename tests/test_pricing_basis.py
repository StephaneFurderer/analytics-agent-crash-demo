"""The Pricing basis in the warehouse, read through the Metric layer.

The full-warehouse tests compare against the generator's pricing configuration,
which ADR 0002 allows (it is the Pricing basis, not the hidden model).
"""

import pytest

from compass import metrics
from compass.generator import pricing


def _as_dict(frame, component):
    rows = frame[frame.component == component]
    return dict(zip(rows.term, rows.coefficient))


def test_the_warehouse_holds_the_2025_pricing_glm_and_no_other_model(full_con):
    basis = metrics.pricing_basis(full_con)

    assert set(basis.model) == {pricing.PRICING_GLM_2025.name}
    assert _as_dict(basis, "frequency") == dict(pricing.PRICING_GLM_2025.frequency)
    assert _as_dict(basis, "severity") == dict(pricing.PRICING_GLM_2025.severity)
    assert _as_dict(basis, "premium") == {
        "post_departure_share": pricing.PRICING_GLM_2025.post_departure_share,
        "expense_load": pricing.PRICING_GLM_2025.expense_load,
    }
