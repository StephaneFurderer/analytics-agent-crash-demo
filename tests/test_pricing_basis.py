"""The Pricing basis in the warehouse, read through the Metric layer.

The full-warehouse tests compare against the generator's pricing configuration,
which ADR 0002 allows (it is the Pricing basis, not the hidden model).
"""

import math

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


EXPECTED = ["expected_claim_count", "expected_claim_frequency", "expected_average_severity"]


def test_expected_values_by_segment_follow_the_pricing_glm(tiny_book):
    result = metrics.query(tiny_book, EXPECTED, by=["segment"]).set_index("segment")

    # B3-F: holiday_travelers, age 42, CA, departs in January, flight, trip cost 800.
    freq = math.exp(-3.0 + 0.1 * 0.2 + 0.2 * math.log(800) + 0.3 + 0.4 + 0.5 + 0.6)
    pre = math.exp(4.0 + 0.05 * 0.2 + 0.3 * math.log(800) - 0.2)
    post = pre * math.exp(-0.5)
    holiday = result.loc["holiday_travelers"]
    assert holiday.expected_claim_count == pytest.approx(freq)
    assert holiday.expected_claim_frequency == pytest.approx(freq)  # one Policy
    assert holiday.expected_average_severity == pytest.approx(0.6 * pre + 0.4 * post)

    # baseline holds B2-H (age 35, TX, July, hotel, trip cost 500) and B4-H (age 50, FL, September,
    # hotel, trip cost 7000): every categorical term is a reference level.
    freq_b2 = math.exp(-3.0 + 0.1 * -0.5 + 0.2 * math.log(500))
    pre_b2 = math.exp(4.0 + 0.05 * -0.5 + 0.3 * math.log(500))
    freq_b4 = math.exp(-3.0 + 0.1 * 1.0 + 0.2 * math.log(7000))
    pre_b4 = math.exp(4.0 + 0.05 * 1.0 + 0.3 * math.log(7000))
    mix = 0.6 + 0.4 * math.exp(-0.5)
    baseline = result.loc["baseline"]
    assert baseline.expected_claim_count == pytest.approx(freq_b2 + freq_b4)
    assert baseline.expected_average_severity == pytest.approx(
        (freq_b2 * pre_b2 + freq_b4 * pre_b4) * mix / (freq_b2 + freq_b4)
    )

    # winter_birds holds B1-H and B1-F (two Policies): frequency is per Policy.
    winter = result.loc["winter_birds"]
    assert winter.expected_claim_frequency == pytest.approx(winter.expected_claim_count / 2)


def test_expected_loss_on_the_pricing_basis_equals_each_policys_pure_premium(full_con):
    result = metrics.query(full_con, EXPECTED + ["written_pure_premium"], by=["policy_id"])

    expected_loss = result.expected_claim_count * result.expected_average_severity
    # Pure premium is stored rounded to the cent.
    assert expected_loss.to_numpy() == pytest.approx(result.written_pure_premium.to_numpy(), abs=0.0051)
