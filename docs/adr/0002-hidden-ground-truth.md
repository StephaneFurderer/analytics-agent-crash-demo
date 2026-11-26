# Only the pricing model in the warehouse; the true model stays hidden

The warehouse contains the **Pricing basis** (the 2025 pricing GLM) but never the model that actually generated the claims. The true model, including the 2026 destination **Drift** and the September 2026 hurricane, lives only in the generator's configuration. It is used to derive reference answers for **Benchmark questions** and to test that the generator is correct. The previous version stored the "2026_actual" GLM and precomputed A/E results in the warehouse, so an agent could read the answer instead of finding it. That defeats the point of the demo, and it isn't how a real department works, because nobody knows the true model.

## Consequences

- Nothing in the warehouse, the context layer or the dashboard may read from the generator's true-model configuration. Only the generator, its tests and the benchmark reference answers may use it.
- Precomputed answer tables (the old `dislocation_analysis`) are out of scope by default. Q15 revisits this at build time.
