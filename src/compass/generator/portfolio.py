"""How Compass Assistance's book is sold: segments, mixes, seasonality and trip costs.

This describes the business written, not how claims arise. It is neither the
Pricing basis (`pricing.py`) nor the true model (`truth.py`).
"""

SEGMENTS = ("winter_birds", "holiday_travelers", "baseline")

# Bookings per segment, per Underwriting year.
BOOKINGS_PER_YEAR = {"winter_birds": 12_000, "holiday_travelers": 18_000, "baseline": 20_000}

COVERAGE_TYPES = ("hotel_only", "flight_only", "hotel_and_flight")
COVERAGE_WEIGHTS = {
    "winter_birds": (0.20, 0.10, 0.70),
    "holiday_travelers": (0.15, 0.25, 0.60),
    "baseline": (0.70, 0.10, 0.20),
}

# Departure-month seasonality, January to December.
MONTH_WEIGHTS = {
    "winter_birds": (0.20, 0.18, 0.12, 0.02, 0.01, 0.01, 0.01, 0.01, 0.02, 0.08, 0.15, 0.19),
    "holiday_travelers": (0.03, 0.04, 0.10, 0.08, 0.05, 0.12, 0.14, 0.10, 0.03, 0.04, 0.12, 0.15),
    "baseline": (0.06, 0.06, 0.08, 0.08, 0.09, 0.10, 0.11, 0.10, 0.08, 0.08, 0.08, 0.08),
}

# Age: truncated normal (mean, std, low, high), or uniform (low, high) when mean is None.
AGE = {
    "winter_birds": (67, 8, 50, 85),
    "holiday_travelers": (42, 10, 25, 65),
    "baseline": (None, None, 25, 70),
}

# Trip nights: lognormal around a median (median, sigma, low, high).
NIGHTS = {
    "winter_birds": (30, 0.5, 14, 56),
    "holiday_travelers": (6, 0.4, 3, 10),
    "baseline": (3.5, 0.3, 2, 7),
}

# Days of advance purchase before departure: truncated normal (mean, std, low, high).
ADVANCE_DAYS = {
    "winter_birds": (90, 30, 14, 180),
    "holiday_travelers": (60, 25, 7, 150),
    "baseline": (30, 20, 3, 120),
}

REGION_WEIGHTS = {  # us_atlantic, gulf_coast, caribbean
    "winter_birds": (0.45, 0.30, 0.25),
    "holiday_travelers": (0.25, 0.15, 0.60),
    "baseline": (0.40, 0.25, 0.35),
}

STATES = ("NY", "NJ", "CT", "MA", "PA", "OH", "MI", "IL", "MN", "WI",
          "FL", "TX", "CA", "GA", "VA", "NC", "CO", "AZ", "WA", "MD")
STATE_WEIGHTS = {
    "winter_birds": (0.18, 0.10, 0.08, 0.10, 0.10, 0.08, 0.08, 0.08, 0.06, 0.05,
                     0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.005, 0.005),
    "holiday_travelers": (0.10, 0.06, 0.03, 0.05, 0.06, 0.05, 0.03, 0.08, 0.01, 0.01,
                          0.08, 0.10, 0.12, 0.05, 0.04, 0.04, 0.02, 0.02, 0.02, 0.03),
    "baseline": tuple(1 / 20 for _ in range(20)),
}

PEAK_MONTHS = (1, 2, 3, 6, 7, 8, 11, 12)
HOTEL_PEAK_UPLIFT = 0.30
HOTEL_RATE_NOISE = (0.85, 1.15)
FLIGHT_FARE = {"caribbean": (400, 900), "other": (200, 600)}
FLIGHT_PEAK_UPLIFT = 0.25
FLIGHT_ADVANCE_DISCOUNT = 0.15  # at 180 days ahead, prorated
