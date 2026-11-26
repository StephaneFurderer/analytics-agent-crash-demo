"""The local DuckDB warehouse (ADR 0001).

`write` builds a warehouse from scratch out of base-table rows. `reset` does the
same from the seeded generator. Both always start from an empty file, so a
warehouse is fully determined by its input.

The file holds the base tables only: it is what the Analytics agent connects to,
and before Chapter 6 the agent must not find the Metric layer there. Readers that
need metrics (the dashboard, tests, benchmark reference answers) open it with
`compass.metrics.connect`, which applies the Metric layer per connection.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd

DEFAULT_PATH = Path("warehouse/compass.duckdb")
DEFAULT_SEED = 42
# Environment variable that points the dashboard (and tests) at a warehouse file.
PATH_ENV = "COMPASS_WAREHOUSE"


def default_path() -> Path:
    """The warehouse file: $COMPASS_WAREHOUSE, else warehouse/compass.duckdb under the current directory."""
    return Path(os.environ.get(PATH_ENV, DEFAULT_PATH))

# Base tables in load order (parents before children).
TABLES = ("destinations", "bookings", "policies", "claims", "pricing_coefficients")

Rows = pd.DataFrame | Iterable[Mapping]


def write(path: str | Path, **tables: Rows) -> Path:
    """Create a fresh warehouse at `path` holding the base-table rows `tables` (base tables only)."""
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
                rows = as_frame(tables[name])
                columns = ", ".join(rows.columns)
                con.register("_rows", rows)
                con.execute(f"INSERT INTO {name} ({columns}) SELECT {columns} FROM _rows")
                con.unregister("_rows")
    finally:
        con.close()
    return path


def reset(path: str | Path, seed: int = DEFAULT_SEED) -> Path:
    """Rebuild the warehouse from scratch with the seeded generator."""
    from compass.generator import generate_book

    return write(path, **generate_book(seed))


def connect(path: str | Path) -> duckdb.DuckDBPyConnection:
    """Open the warehouse file read-only, the way the Analytics agent sees it: base tables only.

    For metrics, use `compass.metrics.connect`.
    """
    return duckdb.connect(str(path), read_only=True)


def as_frame(rows: Rows) -> pd.DataFrame:
    """Rows (a DataFrame, or dicts) as a DataFrame."""
    return rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
