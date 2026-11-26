# analytics-agent-crash-demo

A follow-along demo built around the fictional travel insurer **Compass Assistance**.

## Quick start

Install [uv](https://docs.astral.sh/uv/), then from the repo root:

```sh
uv run demo reset       # build the local DuckDB warehouse from the seed
uv run demo dashboard   # open the Legacy dashboard
uv run pytest           # run the tests (no API key needed)
```

`uv` installs the pinned Python version and all dependencies on first run. The warehouse is written to
`warehouse/compass.duckdb` (override with `--path` or `COMPASS_WAREHOUSE`) and is never committed.
