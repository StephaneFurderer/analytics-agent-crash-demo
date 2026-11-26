"""The true model: how Compass Assistance's claims actually arise. HIDDEN GROUND TRUTH.

ADR 0002: only the generator, its tests and the benchmark reference answers may
import this module. The warehouse loader, the Metric layer, the Context layer and
the Legacy dashboard must never read it. A test enforces this for `compass`
modules outside `compass.generator`.

The true model is the 2025 pricing GLM, plus the 2026
destination Drift (`TRUE_MODEL[2026]`) and the September 2026 Gulf Coast hurricane (`HURRICANE`).
"""

from dataclasses import dataclass, replace
from datetime import date
from types import MappingProxyType

from compass.generator.pricing import GLM, PRICING_GLM_2025

# The 2026 destination Drift: extra claim frequency (log scale) in two regions that the
# Pricing basis lacks. Sized so that 2026 A/E on Ultimate is clearly above 1 there.
DESTINATION_DRIFT_2026 = MappingProxyType({"caribbean": 0.35, "gulf_coast": 0.40})

# True claims model per Underwriting year.
TRUE_MODEL: dict[int, GLM] = {
    2025: PRICING_GLM_2025,  # the pricing worked in 2025: A/E is about 1
    2026: replace(PRICING_GLM_2025, name="2026 true model", region_frequency=DESTINATION_DRIFT_2026),
}


@dataclass(frozen=True)
class ClaimProcess:
    """How individual claims scatter around the true model's means, and when they are reported."""
    severity_shape: float  # Gamma shape; coefficient of variation is 1 / sqrt(shape)
    reporting_lag_days: tuple[float, float]  # lognormal (median, sigma) of days from loss to report


CLAIM_PROCESS = ClaimProcess(severity_shape=2.0, reporting_lag_days=(21.0, 1.0))


@dataclass(frozen=True)
class Hurricane:
    """A catastrophe event: Policies in one destination region exposed at landfall claim at a high rate.

    A Policy is exposed if it was purchased before landfall and is either on its trip at landfall
    (an interruption, post-departure claim) or departs within `cancellation_window_days` after it
    (a cancellation, pre-departure claim). Each exposed Policy claims with `claim_probability`, for a
    Gamma share of its trip cost, lost on the landfall date. Event claims are reported slowly.
    """
    region: str
    landfall: date
    cancellation_window_days: int
    claim_probability: float
    loss_share: tuple[float, float]  # mean share of trip cost: (interruption, cancellation)
    loss_shape: float  # Gamma shape of the amount around its mean
    reporting_lag_days: tuple[float, float]  # lognormal (median, sigma) of days from loss to report


# The September 2026 Gulf Coast hurricane, two weeks before the Valuation date (30 September 2026).
# Sized to add about 40% to the region's 2026 Ultimate, with only a few percent of it reported by then.
HURRICANE = Hurricane(region="gulf_coast", landfall=date(2026, 9, 16), cancellation_window_days=14,
                      claim_probability=0.3, loss_share=(0.35, 0.7), loss_shape=4.0,
                      reporting_lag_days=(40.0, 0.6))
