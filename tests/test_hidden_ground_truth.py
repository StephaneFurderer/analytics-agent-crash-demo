"""ADR 0002: the true model stays hidden from the warehouse, Metric layer and dashboard."""

from pathlib import Path

import compass

SRC = Path(compass.__file__).parent


def test_only_the_generator_reads_the_true_model():
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*")
        if path.suffix in {".py", ".sql"}
        and "generator" not in path.relative_to(SRC).parts
        and "truth" in path.read_text()
    ]
    assert offenders == []


def test_the_warehouse_holds_no_true_model(full_con):
    names = {row[0] for row in full_con.sql("SELECT table_name FROM information_schema.tables").fetchall()}
    assert not any("truth" in n or "true_model" in n for n in names)


def test_the_only_model_stored_is_the_pricing_basis_without_the_destination_effect(full_con):
    from compass.generator.pricing import PRICING_GLM_2025, coefficients_frame

    def ordered(frame):
        return frame.sort_values(["component", "term"]).reset_index(drop=True)

    stored = full_con.sql("SELECT model, component, term, coefficient FROM pricing_coefficients").df()
    assert ordered(stored).equals(ordered(coefficients_frame(PRICING_GLM_2025)))
    assert not stored.term.str.contains("caribbean|gulf|region|destination").any()


def test_no_table_view_or_column_is_named_after_the_destination_effect(full_con):
    columns = full_con.sql("SELECT table_name, column_name FROM information_schema.columns").df()
    names = {n.lower() for n in set(columns.table_name) | set(columns.column_name)}
    assert not any(word in n for n in names for word in ("drift", "region_frequency", "destination_effect"))
