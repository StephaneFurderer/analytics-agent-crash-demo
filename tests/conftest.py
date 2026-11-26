"""Fixtures for both pytest seams.

- `tiny_book`: a connection to a warehouse built from a tiny hand-built book (Seam 1).
- `full_warehouse`: the path of a full seeded warehouse, built once per session.
"""

from datetime import date

import pytest

from compass import warehouse

DESTINATIONS = [
    {"destination_id": 1, "city": "Miami Beach", "state_or_country": "FL", "region": "us_atlantic",
     "airport_code": "MIA", "hotel_rate": 280.0},
    {"destination_id": 2, "city": "Galveston", "state_or_country": "TX", "region": "gulf_coast",
     "airport_code": "IAH", "hotel_rate": 170.0},
    {"destination_id": 3, "city": "Nassau", "state_or_country": "Bahamas", "region": "caribbean",
     "airport_code": "NAS", "hotel_rate": 320.0},
]

BOOKINGS = [
    # A hotel-and-flight booking: one Booking, two Policies.
    {"booking_id": "B1", "segment": "winter_birds", "destination_id": 1, "age": 70,
     "state_of_residence": "NY", "coverage_type": "hotel_and_flight",
     "purchase_date": date(2025, 1, 10), "departure_date": date(2025, 2, 1),
     "return_date": date(2025, 3, 3), "num_nights": 30},
    {"booking_id": "B2", "segment": "baseline", "destination_id": 2, "age": 35,
     "state_of_residence": "TX", "coverage_type": "hotel_only",
     "purchase_date": date(2025, 6, 1), "departure_date": date(2025, 7, 1),
     "return_date": date(2025, 7, 4), "num_nights": 3},
    {"booking_id": "B3", "segment": "holiday_travelers", "destination_id": 3, "age": 42,
     "state_of_residence": "CA", "coverage_type": "flight_only",
     "purchase_date": date(2025, 11, 20), "departure_date": date(2026, 1, 5),
     "return_date": date(2026, 1, 12), "num_nights": 7},
]

POLICIES = [
    {"policy_id": "B1-H", "booking_id": "B1", "product": "hotel", "trip_cost": 9000.0,
     "pure_premium": 100.00, "commercial_premium": 111.00},
    {"policy_id": "B1-F", "booking_id": "B1", "product": "flight", "trip_cost": 600.0,
     "pure_premium": 20.00, "commercial_premium": 22.20},
    {"policy_id": "B2-H", "booking_id": "B2", "product": "hotel", "trip_cost": 500.0,
     "pure_premium": 10.00, "commercial_premium": 11.10},
    {"policy_id": "B3-F", "booking_id": "B3", "product": "flight", "trip_cost": 800.0,
     "pure_premium": 30.00, "commercial_premium": 33.30},
]

# A tiny Pricing basis. Terms not listed (segment_baseline, state_TX, month_7, ...) are reference levels.
PRICING_COEFFICIENTS = [
    {"model": "tiny pricing GLM", "component": c, "term": t, "coefficient": v}
    for c, t, v in [
        ("frequency", "intercept", -3.0), ("frequency", "age", 0.1), ("frequency", "log_trip_cost", 0.2),
        ("frequency", "product_flight", 0.3), ("frequency", "segment_holiday_travelers", 0.4),
        ("frequency", "state_CA", 0.5), ("frequency", "month_1", 0.6),
        ("severity", "intercept", 4.0), ("severity", "age", 0.05), ("severity", "log_trip_cost", 0.3),
        ("severity", "product_flight", -0.2), ("severity", "post_departure", -0.5),
        ("premium", "post_departure_share", 0.4), ("premium", "expense_load", 1.1),
    ]
]


@pytest.fixture(scope="session")
def full_warehouse(tmp_path_factory):
    """The full seeded warehouse, built once per test session."""
    return warehouse.reset(tmp_path_factory.mktemp("full") / "compass.duckdb", seed=warehouse.DEFAULT_SEED)


@pytest.fixture
def full_con(full_warehouse):
    con = warehouse.connect(full_warehouse)
    yield con
    con.close()


@pytest.fixture
def tiny_book(tmp_path):
    path = tmp_path / "tiny.duckdb"
    warehouse.write(path, destinations=DESTINATIONS, bookings=BOOKINGS, policies=POLICIES,
                    pricing_coefficients=PRICING_COEFFICIENTS)
    con = warehouse.connect(path)
    yield con
    con.close()
