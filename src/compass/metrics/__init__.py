"""The Metric layer: SQL definitions in DuckDB, applied on top of the base tables.

The definitions live in `sql/*.sql`, applied in file-name order. Each file creates
the views it needs and registers its metrics in `metric_definitions`. `query` is
the only way the Legacy dashboard reads numbers: it looks up each metric's
expression in the catalogue and groups it by the requested dimensions.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from functools import reduce
from importlib import resources

import duckdb
import pandas as pd

# Placeholder in a catalogue view name for the date a metric is measured on (see `query`'s `on`).
ON_DATE = "on_date"


def standard_development_factors() -> pd.DataFrame:
    """The standard development factors: version-controlled assumption data an actuary edits.

    One row per maturity (months from the departure month to the Valuation month), with the
    Ultimate-to-Incurred factor for claim counts and for claim amounts. A Policy uses the row with
    the largest maturity at or below its own (the first row below that). See the CSV's directory.
    """
    with resources.files("compass.assumptions").joinpath("development_factors.csv").open() as f:
        return pd.read_csv(f, comment="#")


def standard_hurricane_loading() -> pd.DataFrame:
    """The hurricane loading: version-controlled Expert-judgment assumption data, separate from the factors.

    One row per event: event, destination_region, event_date, and the loading per Policy at risk in that
    region on that date: count_per_policy (claims) and amount_per_trip_cost (losses / trip cost).
    """
    with resources.files("compass.assumptions").joinpath("hurricane_loading.csv").open() as f:
        return pd.read_csv(f, comment="#", parse_dates=["event_date"])


def apply(con: duckdb.DuckDBPyConnection, development_factors: pd.DataFrame | None = None,
          hurricane_loading: pd.DataFrame | None = None) -> None:
    """Create the Metric layer's views and catalogue on a warehouse connection.

    The assumption data (`development_factors`, default `standard_development_factors()`, and
    `hurricane_loading`, default `standard_hurricane_loading()`) is exposed to the SQL files as the
    relations `_development_factors` and `_hurricane_loading`.
    """
    if development_factors is None:
        development_factors = standard_development_factors()
    if hurricane_loading is None:
        hurricane_loading = standard_hurricane_loading()
    con.register("_development_factors", development_factors)
    con.register("_hurricane_loading", hurricane_loading)
    try:
        sql_dir = resources.files("compass.metrics").joinpath("sql")
        for sql_file in sorted(sql_dir.iterdir(), key=lambda f: f.name):
            if sql_file.name.endswith(".sql"):
                con.execute(sql_file.read_text())
    finally:
        con.unregister("_development_factors")
        con.unregister("_hurricane_loading")


def definitions(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The metric catalogue, one row per metric."""
    return con.sql("SELECT * FROM metric_definitions ORDER BY metric").df()


def pricing_basis(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The Pricing basis's coefficients: model, component, term, coefficient."""
    return con.sql("SELECT * FROM metric_pricing_basis").df()


def development_factors(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The development factors this warehouse uses: maturity_months, count_factor, amount_factor."""
    return con.sql("SELECT * FROM metric_development_factors ORDER BY maturity_months").df()


def hurricane_loading(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The hurricane loading this warehouse uses: event, destination_region, event_date, count_per_policy,
    amount_per_trip_cost."""
    return con.sql("SELECT * FROM metric_hurricane_loading ORDER BY event_date, event").df()


def ae_bands(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """The A/E bands in order: band, upper_bound (inclusive; NaN for the last), description."""
    return con.sql("SELECT * FROM metric_ae_bands ORDER BY upper_bound NULLS LAST").df()


def ae_band(con: duckdb.DuckDBPyConnection, ae: float) -> str:
    """The A/E band label ('adequate', 'watch' or 'inadequate') for an A/E value."""
    return con.execute("SELECT ae_band(?::DOUBLE)", [float(ae)]).fetchone()[0]


def exposure(con: duckdb.DuckDBPyConnection, on: date, by: Sequence[str] = (),
             where: str | None = None) -> pd.DataFrame:
    """Trip cost at risk on the date `on` (`exposure`) and the number of Policies at risk, by `by`."""
    return query(con, ["exposure", "policies_at_risk"], by=by, where=where, on=on)


def query(
    con: duckdb.DuckDBPyConnection,
    metrics: Sequence[str],
    by: Sequence[str] = (),
    where: str | None = None,
    on: date | None = None,
) -> pd.DataFrame:
    """Compute `metrics` broken down by the dimension columns `by`.

    `where` is an optional SQL filter applied to every metric's view. `on` is the date for metrics
    measured on a date (their view takes `on_date`, e.g. exposure); other metrics ignore it.
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
        if ON_DATE in view_name:
            if on is None:
                raise ValueError(f"metrics {list(group.index)} are measured on a date: pass on=<date>")
            view_name = view_name.replace(ON_DATE, f"DATE '{on.isoformat()}'")
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
