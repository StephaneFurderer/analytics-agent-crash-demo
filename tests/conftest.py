"""Fixtures for both pytest seams.

- `tiny_book`: a connection to a warehouse built from a tiny hand-built book (Seam 1).
- `full_warehouse`: the path of a full seeded warehouse, built once per session.

Plus helpers the benchmark report tests share: fixture Benchmark questions and `nao test` results files.
"""

import json
from datetime import date

import pytest

from compass import cli, keys, metrics, warehouse


@pytest.fixture(autouse=True)
def no_real_secrets(monkeypatch, tmp_path_factory):
    """Tests never see the developer's keys: no shell LLM variables, no repo .env, no Infisical session."""
    for name in [*(n for p in keys.PROVIDERS.values() for n in p.key_names), keys.PROVIDER_ENV,
                 "INFISICAL_TOKEN", "INFISICAL_ENV", "INFISICAL_PROJECT_ID", "INFISICAL_API_URL",
                 "INFISICAL_PROJECT", "INFISICAL_SECRET_PATH"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(keys, "DOTENV", tmp_path_factory.mktemp("no-dotenv") / ".env")
    monkeypatch.setattr(keys.Infisical, "from_session", classmethod(lambda cls: None))

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
    # Purchased in 2026 and still on risk at the Valuation date (2026-09-30): of its 40 days from purchase
    # to return (both included), 20 have passed by the end of the Valuation date, so half is earned.
    {"booking_id": "B4", "segment": "baseline", "destination_id": 1, "age": 50,
     "state_of_residence": "FL", "coverage_type": "hotel_only",
     "purchase_date": date(2026, 9, 11), "departure_date": date(2026, 9, 25),
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

# Claims are paid in full when reported, so every Case reserve is zero.
# Only claims reported by the Valuation date exist.
CLAIMS = [
    {"claim_id": "C1", "policy_id": "B1-H", "claim_type": "pre_departure", "loss_date": date(2025, 1, 20),
     "report_date": date(2025, 1, 25), "paid_amount": 4000.00, "case_reserve": 0.0},
    {"claim_id": "C2", "policy_id": "B1-F", "claim_type": "post_departure", "loss_date": date(2025, 2, 10),
     "report_date": date(2025, 3, 15), "paid_amount": 250.00, "case_reserve": 0.0},
    {"claim_id": "C3", "policy_id": "B2-H", "claim_type": "post_departure", "loss_date": date(2025, 7, 2),
     "report_date": date(2025, 8, 1), "paid_amount": 300.00, "case_reserve": 0.0},
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
        ("premium", "expense_load", 1.1),
    ]
]

# Tiny standard development factors (Ultimate / Incurred), a step function of maturity in months from the
# departure month to the Valuation month: a Policy uses the row with the largest maturity at or below its own.
# Maturities: B1 departs Feb 2025 (19), B2 Jul 2025 (14), B3 Jan 2026 (8), B4 Sep 2026 (0).
DEVELOPMENT_FACTORS = [
    {"maturity_months": 0, "count_factor": 2.0, "amount_factor": 2.5},
    {"maturity_months": 6, "count_factor": 1.5, "amount_factor": 1.6},
    {"maturity_months": 12, "count_factor": 1.1, "amount_factor": 1.2},
    {"maturity_months": 18, "count_factor": 1.0, "amount_factor": 1.0},
]

# A tiny hurricane loading (Expert judgment): a made-up Gulf Coast storm on 2 July 2025, when only B2-H
# (Galveston, trip cost 500) is at risk there. Loading per Policy at risk: 0.5 claims and 0.4 of its trip cost.
HURRICANE_LOADING = [
    {"event": "tiny storm", "destination_region": "gulf_coast", "event_date": date(2025, 7, 2),
     "count_per_policy": 0.5, "amount_per_trip_cost": 0.4},
]


@pytest.fixture(scope="session")
def full_warehouse(tmp_path_factory):
    """The full seeded warehouse, built once per test session."""
    return warehouse.reset(tmp_path_factory.mktemp("full") / "compass.duckdb", seed=warehouse.DEFAULT_SEED)


@pytest.fixture
def full_con(full_warehouse):
    con = metrics.connect(full_warehouse)
    yield con
    con.close()


@pytest.fixture
def tiny_book(tmp_path):
    path = tmp_path / "tiny.duckdb"
    warehouse.write(path, destinations=DESTINATIONS, bookings=BOOKINGS, policies=POLICIES, claims=CLAIMS,
                    pricing_coefficients=PRICING_COEFFICIENTS)
    con = metrics.connect(path, development_factors=DEVELOPMENT_FACTORS, hurricane_loading=HURRICANE_LOADING)
    yield con
    con.close()


# Benchmark report helpers (test_benchmark_report.py, test_exploratory.py).

def question(tests_dir, folder, name, tier, set_name):
    path = tests_dir / folder / f"{name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: {name}\nprompt: What is {name}?\ntags: [tier:{tier}, set:{set_name}]\n"
        f"sql: SELECT 1 AS answer\n"
    )


def nao_results(results_dir, chapter, set_name, runs, stamp="20261126_120000"):
    """A results file shaped like `nao test`'s, archived where `demo benchmark` puts it.

    `runs` maps a question name to the pass/fail of each attempt.
    """
    path = results_dir / f"ch{chapter}" / set_name / f"results_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    results = [
        {"name": name, "model": "anthropic:claude-opus-5-5", "passed": passed, "message": "", "tokens": 1000,
         "cost": 0.05, "duration_ms": 1, "tool_call_count": 1, "error": None, "details": None, "attempt": i}
        for name, attempts in runs.items()
        for i, passed in enumerate(attempts, start=1)
    ]
    path.write_text(json.dumps({"timestamp": "2026-11-26T12:00:00", "results": results}))
    return path


def matrix_rows(markdown, heading):
    """The table under `heading` in the report, as {first cell: [other cells]}."""
    lines = markdown.split(heading, 1)[1].splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|"))
    table = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        if not set(line) <= set("|-: "):
            table.append([cell.strip() for cell in line.strip("|").split("|")])
    header, *rows = table
    return header, {row[0]: row[1:] for row in rows}


def run_report(tmp_path, tests_dir, results_dir):
    out = tmp_path / "report"
    code = cli.main(["report", "--questions", str(tests_dir), "--results", str(results_dir), "--out", str(out)])
    return code, out
