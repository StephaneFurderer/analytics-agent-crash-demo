"""Recovering the true model from the data (ticket #8).

Refit the frequency (Poisson) and severity (Gamma) GLMs, log link, on a fully developed generated book and check
that they recover the true coefficients, the 2026 destination Drift included, and find nothing else: terms the
true model doesn't have (an Underwriting-year level, region effects on 2025 or on severity) come back at zero.

Fully developed = the seeded book's Bookings and Policies, with every claim of the true model's claim stream
(`STREAM_CLAIMS`) regenerated with a Valuation date far in the future, so none is still unreported. The September
2026 hurricane (its own stream) is a catastrophe event outside the GLMs and is left out. As ADR 0002 allows, this
test reads the true model (`truth.TRUE_MODEL`); nothing it builds goes into the warehouse.

Tolerance: each refit coefficient must be within 4 standard errors of its true value, the standard errors coming
from the fit's own Fisher information (the severity one scaled by the Pearson dispersion). 4 SE keeps the chance of
a false failure across all ~45 coefficients near 0.3% for an unlucky seed while still catching any real misfit, and
the test also checks the standard errors are small enough (e.g. under 0.1 on the Drift terms) for that to mean
something. The intercept on its own is loose (it trades off against log_trip_cost), so the overall level is pinned
separately: observed total / the true model's expected total must be within 4 SE of 1 (a 10% level error fails).
Severity is capped at the trip cost in the generator (about 1.6% of claims), a small bias the 4 SE allow.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from compass import warehouse
from compass.generator import STREAM_BOOKINGS, STREAM_CLAIMS, UNDERWRITING_YEARS, VALUATION_DATE, rng_for
from compass.generator.book import destinations_frame, generate_year
from compass.generator.claims import generate_claims
from compass.generator.truth import CLAIM_PROCESS, TRUE_MODEL

FULLY_DEVELOPED = date(2035, 12, 31)
TOLERANCE_SE = 4.0
DRIFT_YEAR = 2026
REGIONS = ("caribbean", "gulf_coast")  # reference: us_atlantic


@pytest.fixture(scope="module")
def developed_book():
    """(policies with rating features, every claim) for each Underwriting year, from the seeded streams."""
    seed = warehouse.DEFAULT_SEED
    destinations = destinations_frame()
    policies, claims = [], []
    for year in UNDERWRITING_YEARS:
        purchased_until = min(date(year, 12, 31), VALUATION_DATE)
        b, p = generate_year(rng_for(seed, year, STREAM_BOOKINGS), year, purchased_until, destinations)
        c = generate_claims(rng_for(seed, year, STREAM_CLAIMS), year, b, p, destinations, TRUE_MODEL[year],
                            CLAIM_PROCESS, FULLY_DEVELOPED)
        p = (p.merge(b, on="booking_id").merge(destinations[["destination_id", "region"]], on="destination_id"))
        p["underwriting_year"] = year
        policies.append(p)
        claims.append(c)
    return pd.concat(policies, ignore_index=True), pd.concat(claims, ignore_index=True)


def _rating_terms(frame: pd.DataFrame, terms) -> pd.DataFrame:
    """Design-matrix columns for the documented rating terms (see `generator.pricing`), from raw columns."""
    months = pd.to_datetime(frame.departure_date).dt.month
    x = pd.DataFrame(index=frame.index)
    for term in terms:
        if term == "intercept":
            x[term] = 1.0
        elif term == "age":
            x[term] = (frame.age - 40) / 10
        elif term == "log_trip_cost":
            x[term] = np.log(frame.trip_cost)
        elif term == "product_flight":
            x[term] = frame["product"].eq("flight").astype(float)
        elif term == "post_departure":
            x[term] = frame.claim_type.eq("post_departure").astype(float)
        elif term.startswith("segment_"):
            x[term] = frame.segment.eq(term.removeprefix("segment_")).astype(float)
        elif term.startswith("state_"):
            x[term] = frame.state_of_residence.eq(term.removeprefix("state_")).astype(float)
        elif term.startswith("month_"):
            x[term] = months.eq(int(term.removeprefix("month_"))).astype(float)
        else:
            raise KeyError(term)
    return x


def _extra_terms(frame: pd.DataFrame, x: pd.DataFrame) -> None:
    """Year and region terms: an Underwriting-year level, region levels, and region x Drift-year interactions."""
    drift_year = frame.underwriting_year.eq(DRIFT_YEAR).astype(float)
    x[f"year_{DRIFT_YEAR}"] = drift_year
    for region in REGIONS:
        in_region = frame.region.eq(region).astype(float)
        x[f"region_{region}"] = in_region
        x[f"region_{region}_{DRIFT_YEAR}"] = in_region * drift_year


def _irls(x: np.ndarray, y: np.ndarray, family: str, iterations: int = 50):
    """Fit a log-link GLM by iteratively reweighted least squares. Returns (coefficients, standard errors)."""
    beta = np.zeros(x.shape[1])
    beta[0] = np.log(y.mean())  # column 0 is the intercept
    for _ in range(iterations):
        mu = np.exp(x @ beta)
        # Log link: Poisson working weight mu, Gamma working weight 1; working response eta + (y - mu) / mu.
        w = mu if family == "poisson" else np.ones_like(mu)
        z = x @ beta + (y - mu) / mu
        xtw = x.T * w
        new = np.linalg.solve(xtw @ x, xtw @ z)
        done = np.max(np.abs(new - beta)) < 1e-10
        beta = new
        if done:
            break
    mu = np.exp(x @ beta)
    w = mu if family == "poisson" else np.ones_like(mu)
    dispersion = 1.0 if family == "poisson" else np.sum(((y - mu) / mu) ** 2) / (len(y) - x.shape[1])
    se = np.sqrt(np.diag(np.linalg.inv((x.T * w) @ x)) * dispersion)
    return beta, se


def _fit(frame, terms, y, family):
    x = _rating_terms(frame, terms)
    _extra_terms(frame, x)
    beta, se = _irls(x.to_numpy(), np.asarray(y, dtype=float), family)
    return pd.DataFrame({"estimate": beta, "se": se}, index=x.columns), x


def _true_coefficients(component: str, index) -> pd.Series:
    """The true model's coefficients on the refit's terms; terms the true model lacks are 0."""
    base, drifted = TRUE_MODEL[2025], TRUE_MODEL[DRIFT_YEAR]
    assert getattr(base, component) == getattr(drifted, component)  # the Drift is not a change in rating terms
    assert not base.region_frequency  # 2025 has no region effect
    true = pd.Series(0.0, index=index)
    for term, value in getattr(base, component).items():
        true[term] = value
    if component == "frequency":
        for region, value in drifted.region_frequency.items():
            true[f"region_{region}_{DRIFT_YEAR}"] = value
    return true


def _level(x: pd.DataFrame, true: pd.Series, y, family: str):
    """Observed total / the true model's expected total on the same rows, and the ratio's standard error.

    The intercept alone is loose (it trades off against log_trip_cost), so this pins the overall level directly.
    """
    mu = np.exp(x.to_numpy() @ true[x.columns].to_numpy())
    variance = mu if family == "poisson" else mu ** 2 / CLAIM_PROCESS.severity_shape
    return np.sum(y) / mu.sum(), np.sqrt(variance.sum()) / mu.sum()


def _assert_recovered(fit: pd.DataFrame, true: pd.Series):
    z = (fit.estimate - true) / fit.se
    report = fit.assign(true=true, z=z).round(3).to_string()
    assert (z.abs() < TOLERANCE_SE).all(), report


def test_the_frequency_refit_recovers_the_true_model_and_the_2026_destination_drift(developed_book):
    policies, claims = developed_book
    counts = claims.policy_id.value_counts().reindex(policies.policy_id, fill_value=0).to_numpy()

    fit, x = _fit(policies, TRUE_MODEL[2025].frequency, counts, "poisson")
    true = _true_coefficients("frequency", fit.index)

    _assert_recovered(fit, true)
    level, se = _level(x, true, counts, "poisson")
    assert abs(level - 1) < TOLERANCE_SE * se, (level, se)
    # The Drift is found, clearly, and only where it is: Caribbean and Gulf Coast, 2026, frequency.
    for region in REGIONS:
        drift = fit.loc[f"region_{region}_{DRIFT_YEAR}"]
        assert drift.se < 0.1, region
        assert drift.estimate > 0.2, region
    assert fit.loc[["age", "log_trip_cost", "product_flight"], "se"].max() < 0.05


def test_the_severity_refit_recovers_the_true_model_with_no_drift(developed_book):
    policies, claims = developed_book
    frame = claims.merge(policies, on="policy_id")

    fit, x = _fit(frame, TRUE_MODEL[2025].severity, frame.paid_amount, "gamma")
    true = _true_coefficients("severity", fit.index)

    _assert_recovered(fit, true)
    level, se = _level(x, true, frame.paid_amount, "gamma")
    assert abs(level - 1) < TOLERANCE_SE * se, (level, se)
    assert fit.se.max() < 0.25
    assert fit.loc[["age", "log_trip_cost", "product_flight", "post_departure"], "se"].max() < 0.05
