# The Metric layer is applied per connection, not stored in the warehouse file

Until Chapter 6 the **Analytics agent** must not see the **Metric layer**, and until Chapter 5 it must not see the hurricane. nao's `exclude: ["*.metric_*"]` only filters what `nao sync` writes into the Context layer: an agent running SQL can still list and query every view and table in the DuckDB file it connects to. So the warehouse file (`warehouse/compass.duckdb`, what `demo reset` writes) holds the base tables only. The Metric layer (views, catalogue, A/E bands, and the Expert-judgment assumptions: development factors and the hurricane loading, read from `compass/assumptions/*.csv`) is applied per connection by `metrics.connect(path)`: an in-memory DuckDB that attaches the file read-only and builds the layer in memory. The Legacy dashboard, the tests and the benchmark's reference answers all read through it.

nao runs each Benchmark question's reference SQL on the file the agent sees, where the `metric_*` views don't exist. `demo benchmark` therefore stages the set first (`benchmark.stage`): it computes each reference answer through `metrics.connect` and hands nao a copy of the question (under the git-ignored `nao/tests/_run/`) whose SQL returns those rows as literals. Question authors still write reference SQL on the `metric_*` views.

## Considered options

- **Persist the layer and rely on the nao exclude**: rejected, it leaks the whole Metric layer and the hurricane loading to a Chapter 2 agent through `SHOW TABLES`.
- **A second, layered warehouse file for the dashboard**: rejected, two files to keep in step for no gain; applying the layer takes milliseconds.

## Consequences

- A test opens the built file plainly and checks it exposes only the base tables, no macros, and no name or value tracing the true model or the hurricane.
- Chapter 6 (the Metric layer joins the Context layer) materialises the layer for the agent by applying it to the file itself after `warehouse.write`: `metrics.apply(duckdb.connect(str(path)))`, for example in `warehouse.reset` from that Chapter's tag on, and drops the nao exclude. Then the base-tables-only test changes with it.
