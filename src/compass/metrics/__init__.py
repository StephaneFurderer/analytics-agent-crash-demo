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


def standard_development_factors() -> pd.DataFrame:
    """The standard development factors: version-controlled assumption data an actuary edits.

    One row per maturity (months from the departure month to the Valuation month), with the
    Ultimate-to-Incurred factor for claim counts and for claim amounts. A Policy uses the row with
    the largest maturity at or below its own (the first row below that). See the CSV's directory.
    """
    with resources.files("compass.assumptions").joinpath("development_factors.csv").open() as f:
        return pd.read_csv(f, comment="#")


def apply(con: duckdb.DuckDBPyConnection, development_factors: pd.DataFrame | None = None) -> None:
    """Create the Metric layer's views and catalogue on a warehouse connection.

    The assumption data (`development_factors`, default `standard_development_factors()`) is
    exposed to the SQL files as the relation `_development_factors`.
    """
    if development_factors is None:
        development_factors = standard_development_factors()
    con.register("_development_factors", development_factors)
    try:
        sql_dir = resources.files("compass.metrics").joinpath("sql")
        for sql_file in sorted(sql_dir.iterdir(), key=lambda f: f.name):
            if sql_file.name.endswith(".sql"):
                con.execute(sql_file.read_text())
    finally:
        con.unregister("_development_factors")


def definitions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The metric catalogue, one row per metric."""
    return con.sql("SELECT * FROM metric_definitions ORDER BY metric").df()


def pricing_basis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The Pricing basis's coefficients: model, component, term, coefficient."""
    return con.sql("SELECT * FROM metric_pricing_basis").df()


def ae_bands(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The A/E bands in order: band, upper_bound (inclusive; NaN for the last), description."""
    return con.sql("SELECT * FROM metric_ae_bands ORDER BY upper_bound NULLS LAST").df()


def ae_band(con: duckdb.DuckDBPyConnection, ae: float) -> str:
    """The A/E band label ('adequate', 'watch' or 'inadequate') for an A/E value."""
    return con.execute("SELECT ae_band(?::DOUBLE)", [float(ae)]).fetchone()[0]


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
