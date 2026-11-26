"""The true model: how Compass Assistance's claims actually arise. HIDDEN GROUND TRUTH.

ADR 0002: only the generator, its tests and the benchmark reference answers may
import this module. The warehouse loader, the Metric layer, the Context layer and
the Legacy dashboard must never read it. A test enforces this for `compass`
modules outside `compass.generator`.

The true model is the 2025 pricing GLM, plus (in later tickets) the 2026
destination Drift and the September 2026 Gulf Coast hurricane.
"""

from dataclasses import dataclass, replace
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
