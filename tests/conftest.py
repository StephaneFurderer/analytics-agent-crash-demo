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
    # Purchased in 2026 and still on risk at the Valuation date (2026-09-30):
    # 20 of its 40 days from purchase to return have passed, so half is earned.
    {"booking_id": "B4", "segment": "baseline", "destination_id": 1, "age": 50,
     "state_of_residence": "FL", "coverage_type": "hotel_only",
     "purchase_date": date(2026, 9, 10), "departure_date": date(2026, 9, 25),
     "return_date": date(2026, 10, 20), "num_nights": 25},
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
    {"policy_id": "B4-H", "booking_id": "B4", "product": "hotel", "trip_cost": 7000.0,
     "pure_premium": 40.00, "commercial_premium": 44.40},
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
    warehouse.write(path, destinations=DESTINATIONS, bookings=BOOKINGS, policies=POLICIES)
    con = warehouse.connect(path)
    yield con
    con.close()
