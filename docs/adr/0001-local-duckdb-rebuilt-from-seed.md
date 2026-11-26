# Local DuckDB rebuilt from a seed, not a hosted database

The warehouse is a local DuckDB file. The seeded generator rebuilds it from scratch on every reset, and the generated data is never committed or hosted. The previous version ran on a hosted Supabase Postgres project, which was paused for inactivity within days. That is fatal for a repo people download and follow months after a recorded talk. DuckDB needs no account, works offline, is supported by nao (`type: duckdb`), and makes `reset` and chapter jumps reproducible byte for byte.

## Considered Options

- **Hosted Postgres (Supabase):** rejected. It can be paused or deleted, needs accounts and secrets, and isn't reproducible for each follower.
- **Postgres in Docker:** rejected. It's an extra moving part for followers, with no benefit at this data size.
- **SQLite:** rejected. nao does not support it as a warehouse.
- **Committing the DuckDB file:** rejected. The generator is the source of truth, and a committed binary would drift from it.
