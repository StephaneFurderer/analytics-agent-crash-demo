"""The local DuckDB warehouse (ADR 0001).

`write` builds a warehouse from scratch out of base-table rows and applies the
Metric layer on top. `reset` does the same from the seeded generator. Both
always start from an empty file, so a warehouse is fully determined by its input.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd

from compass import metrics

DEFAULT_PATH = Path("warehouse/compass.duckdb")
DEFAULT_SEED = 42
# Environment variable that points the dashboard (and tests) at a warehouse file.
PATH_ENV = "COMPASS_WAREHOUSE"


def default_path() -> Path:
    """The warehouse file: $COMPASS_WAREHOUSE, else warehouse/compass.duckdb under the current directory."""
    return Path(os.environ.get(PATH_ENV, DEFAULT_PATH))

# Base tables in load order (parents before children).
TABLES = ("destinations", "bookings", "policies", "pricing_coefficients")

Rows = pd.DataFrame | Iterable[Mapping]


def write(path: str | Path, **tables: Rows) -> Path:
    """Create a fresh warehouse at `path` from base-table rows, then apply the Metric layer."""
    unknown = set(tables) - set(TABLES)
    if unknown:
        raise ValueError(f"unknown base tables: {sorted(unknown)}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for stale in (path, path.with_name(path.name + ".wal")):
        stale.unlink(missing_ok=True)

    con = duckdb.connect(str(path))
    try:
        con.execute(resources.files("compass").joinpath("schema.sql").read_text())
        for name in TABLES:
            if name in tables:
                frame = _frame(tables[name])
                columns = ", ".join(frame.columns)
                con.register("_rows", frame)
                con.execute(f"INSERT INTO {name} ({columns}) SELECT {columns} FROM _rows")
                con.unregister("_rows")
        metrics.apply(con)
    finally:
        con.close()
    return path


def reset(path: str | Path, seed: int = DEFAULT_SEED) -> Path:
    """Rebuild the warehouse from scratch with the seeded generator."""
    from compass.generator import generate_book

    return write(path, **generate_book(seed))


def connect(path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only, the way the dashboard and the agent see it."""
    return duckdb.connect(str(path), read_only=True)


def _frame(rows: Rows) -> pd.DataFrame:
    return rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
