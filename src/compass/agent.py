"""The Analytics agent: a nao project over the local warehouse.

The nao project lives in `nao/` at the repo root. Its config reads the Anthropic
API key from `ANTHROPIC_API_KEY` and points at the default warehouse file.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = REPO_ROOT / "nao"
# The warehouse file the nao config points at (relative to PROJECT_DIR in the config).
WAREHOUSE = REPO_ROOT / "warehouse" / "compass.duckdb"
API_KEY_ENV = "ANTHROPIC_API_KEY"
