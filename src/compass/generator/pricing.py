"""The Pricing basis: the 2025 pricing GLM, as the pricing team set it.

This is the only model allowed in the warehouse (ADR 0002). It prices every
Policy, in both Underwriting years. Anything that loads or displays the pricing
coefficients must read them from here, never copy them by hand.

Frequency (Poisson, log link), claims per Policy:
    log(lambda) = intercept + age * (age - 40) / 10 + log_trip_cost * log(trip_cost)
                  + product_flight [flight] + segment_<s> + state_<st> + month_<departure month>
Severity (Gamma, log link), mean amount per claim:
    log(mu) = intercept + age * (age - 40) / 10 + log_trip_cost * log(trip_cost)
              + product_flight [flight] + post_departure [post-departure claim]
A claim is post-departure (delay, interruption) with probability
`post_departure_share`, otherwise pre-departure (cancellation).

Pure premium = lambda * ((1 - share) * mu_pre + share * mu_post).
Commercial premium = Pure premium * expense_load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GLM:
    name: str
    frequency: Mapping[str, float]
    severity: Mapping[str, float]
    post_departure_share: float
    expense_load: float
    # Extra frequency terms keyed by destination region. Empty on the Pricing basis.
    region_frequency: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({}))


PRICING_GLM_2025 = GLM(
    name="2025 pricing GLM",
    frequency=MappingProxyType({
        "intercept": -4.5,
        "age": 0.02,
        "log_trip_cost": 0.15,
        "product_flight": 0.25,
        "segment_holiday_travelers": 0.55,
        "segment_baseline": 0.90,
        # State of residence, reference PA (and any state not listed).
        "state_NY": 0.18, "state_NJ": 0.18, "state_FL": 0.14, "state_CA": 0.10,
        "state_TX": 0.05, "state_CT": 0.10, "state_MA": 0.05, "state_MD": 0.0,
        "state_OH": -0.10, "state_MN": -0.16, "state_WI": -0.16, "state_MI": -0.10,
        "state_AZ": -0.10, "state_GA": -0.05, "state_VA": -0.05, "state_NC": -0.05,
        "state_CO": 0.0, "state_WA": -0.05, "state_IL": 0.0,
        # Departure month, reference: months not listed.
        "month_6": 0.10, "month_7": 0.15, "month_8": 0.25,
        "month_9": 0.35, "month_10": 0.20, "month_11": 0.10,
    }),
    severity=MappingProxyType({
        "intercept": 3.0,
        "age": 0.01,
        "log_trip_cost": 0.40,
        "product_flight": -0.20,
        "post_departure": -0.30,
    }),
    post_departure_share=0.55,
    expense_load=1.11,
)


def coefficients_frame(glm: GLM) -> pd.DataFrame:
    """The `pricing_coefficients` warehouse rows for `glm`: one row per term."""
    rows = [(component, term, value)
            for component, terms in (("frequency", glm.frequency), ("severity", glm.severity))
            for term, value in terms.items()]
    rows += [("premium", "post_departure_share", glm.post_departure_share),
             ("premium", "expense_load", glm.expense_load)]
    frame = pd.DataFrame(rows, columns=["component", "term", "coefficient"])
    frame.insert(0, "model", glm.name)
    return frame


def frequency(glm: GLM, f: Mapping[str, np.ndarray]) -> np.ndarray:
    """Expected claims per Policy for policy features `f` (arrays of equal length)."""
    c = glm.frequency
    eta = (c["intercept"]
           + c["age"] * (f["age"] - 40) / 10
           + c["log_trip_cost"] * np.log(np.maximum(f["trip_cost"], 1.0))
           + c["product_flight"] * (f["product"] == "flight"))
    eta = eta + _lookup(c, "segment_", f["segment"])
    eta = eta + _lookup(c, "state_", f["state_of_residence"])
    eta = eta + _lookup(c, "month_", f["departure_month"])
    eta = eta + _lookup(glm.region_frequency, "", f["region"])
    return np.exp(eta)


def severity(glm: GLM, f: Mapping[str, np.ndarray], post_departure: np.ndarray | bool) -> np.ndarray:
    """Mean claim amount for policy features `f`, for pre- or post-departure claims."""
    c = glm.severity
    eta = (c["intercept"]
           + c["age"] * (f["age"] - 40) / 10
           + c["log_trip_cost"] * np.log(np.maximum(f["trip_cost"], 1.0))
           + c["product_flight"] * (f["product"] == "flight")
           + c["post_departure"] * np.asarray(post_departure, dtype=float))
    return np.exp(eta)


def pure_premium(glm: GLM, f: Mapping[str, np.ndarray]) -> np.ndarray:
    """Expected loss per Policy under `glm`."""
    share = glm.post_departure_share
    mean_severity = (1 - share) * severity(glm, f, False) + share * severity(glm, f, True)
    return frequency(glm, f) * mean_severity


def _lookup(coefs: Mapping[str, float], prefix: str, values: np.ndarray) -> np.ndarray:
    values = np.asarray(values).astype(str)
    out = np.zeros(len(values))
    for level in np.unique(values):
        out[values == level] = coefs.get(f"{prefix}{level}", 0.0)
    return out
