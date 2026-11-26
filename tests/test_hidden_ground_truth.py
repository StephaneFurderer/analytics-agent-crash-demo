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
