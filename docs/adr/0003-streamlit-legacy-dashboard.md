# Streamlit for the legacy dashboard

The **Legacy dashboard** is a Streamlit app that reads only from the **Metric layer** in DuckDB. That keeps the whole repo in one language (Python, the same as nao and the generator), managed by `uv`, with no Node toolchain for followers. The previous dashboard was Next.js + TypeScript. It needed a lot of code, computed metrics in JavaScript that drifted from their definitions, and was unstable. The dashboard only needs to look like ordinary BI, so a plain-looking Streamlit app suits the role.

## Considered Options

- **Next.js + TypeScript + Recharts (the previous stack):** rejected. It's heavy to build and maintain, adds a second language and toolchain, and metric logic tends to leak into application code.
- **Evidence.dev:** rejected. In November 2026 the open-source core was moving toward a curl-installed CLI and the hosted Evidence Studio, and the current docs did not confirm support for a local DuckDB file. That is a portability risk for a long-lived follow-along repo.
