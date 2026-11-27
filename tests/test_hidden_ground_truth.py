"""ADR 0002: the true model stays hidden from the warehouse, Metric layer and dashboard.

The warehouse file is what the Analytics agent connects to. Before Chapter 6 it holds the base tables only:
the Metric layer (views, catalogue, development factors, hurricane loading) is applied per connection by
`metrics.connect`, so an agent running SQL on the file can't find it (or the hurricane) there.
"""

import duckdb
import pytest

from compass import warehouse

TRACES = ("hurricane", "truth", "true_model", "drift", "region_frequency", "destination_effect", "metric_")


@pytest.fixture
def plain_con(full_warehouse):
    """The warehouse file opened plainly, the way the agent's DuckDB connection sees it."""
    con = duckdb.connect(str(full_warehouse), read_only=True)
    yield con
    con.close()


def test_the_warehouse_file_holds_the_base_tables_only(plain_con):
    relations = plain_con.sql(
        "SELECT table_name, table_type FROM information_schema.tables").fetchall()
    macros = plain_con.sql("SELECT function_name FROM duckdb_functions() WHERE NOT internal").fetchall()

    assert sorted(relations) == sorted((t, "BASE TABLE") for t in warehouse.TABLES)
    assert macros == []


def test_no_name_or_value_in_the_warehouse_file_traces_the_true_model_or_the_hurricane(plain_con):
    columns = plain_con.sql(
        "SELECT table_name, column_name, data_type FROM information_schema.columns").fetchall()
    names = {n.lower() for table, column, _ in columns for n in (table, column)}
    assert not [n for n in names if any(word in n for word in TRACES)]

    for table, column, data_type in columns:
        if data_type == "VARCHAR":
            hits = plain_con.sql(
                f"SELECT count(*) FROM {table} WHERE " + " OR ".join(
                    f"lower({column}) LIKE '%{word}%'" for word in TRACES)).fetchone()[0]
            assert hits == 0, (table, column)


def test_the_only_model_stored_is_the_pricing_basis_without_the_destination_effect(plain_con):
    from compass.generator.pricing import PRICING_GLM_2025, coefficients_frame

    def ordered(frame):
        return frame.sort_values(["component", "term"]).reset_index(drop=True)

    stored = plain_con.sql("SELECT model, component, term, coefficient FROM pricing_coefficients").df()
    assert ordered(stored).equals(ordered(coefficients_frame(PRICING_GLM_2025)))
    assert not stored.term.str.contains("caribbean|gulf|region|destination").any()
