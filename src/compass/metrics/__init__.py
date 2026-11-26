"""The Metric layer: SQL definitions in DuckDB, applied on top of the base tables.

The definitions live in `sql/*.sql`, applied in file-name order. Each file creates
the views it needs and registers its metrics in `metric_definitions`. `query` is
the only way the Legacy dashboard reads numbers: it looks up each metric's
expression in the catalogue and groups it by the requested dimensions.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import reduce
from importlib import resources

import duckdb
import pandas as pd


def apply(con: duckdb.DuckDBPyConnection) -> None:
    """Create the Metric layer's views and catalogue on a warehouse connection."""
    sql_dir = resources.files("compass.metrics").joinpath("sql")
    for sql_file in sorted(sql_dir.iterdir(), key=lambda f: f.name):
        if sql_file.name.endswith(".sql"):
            con.execute(sql_file.read_text())


def definitions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The metric catalogue, one row per metric."""
    return con.sql("SELECT * FROM metric_definitions ORDER BY metric").df()


def pricing_basis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The Pricing basis's coefficients: model, component, term, coefficient."""
    return con.sql("SELECT * FROM metric_pricing_basis").df()


def query(
    con: duckdb.DuckDBPyConnection,
    metrics: Sequence[str],
    by: Sequence[str] = (),
    where: str | None = None,
) -> pd.DataFrame:
    """Compute `metrics` broken down by the dimension columns `by`.

    `where` is an optional SQL filter applied to every metric's view.
    """
    catalogue = definitions(con).set_index("metric")
    missing = [m for m in metrics if m not in catalogue.index]
    if missing:
        raise KeyError(f"unknown metrics: {missing}")

    by = list(by)
    dims = ", ".join(by)
    frames = []
    for view_name, group in catalogue.loc[list(metrics)].groupby("view_name", sort=False):
        select = [f"{row.expression} AS {name}" for name, row in group.iterrows()]
        sql = f"SELECT {', '.join(by + select)} FROM {view_name}"
        if where:
            sql += f" WHERE {where}"
        if by:
            sql += f" GROUP BY {dims}"
        frames.append(con.sql(sql).df())

    if by:
        result = reduce(lambda a, b: a.merge(b, on=by, how="outer"), frames)
        result = result.sort_values(by).reset_index(drop=True)
    else:
        result = pd.concat(frames, axis=1)
    return result[by + list(metrics)]
