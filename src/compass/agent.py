"""The Analytics agent: a nao project over the local warehouse.

The nao project lives in `nao/` at the repo root. Its config reads the Anthropic
API key from `ANTHROPIC_API_KEY` and points at the default warehouse file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = REPO_ROOT / "nao"
# The warehouse file the nao config points at (relative to PROJECT_DIR in the config).
WAREHOUSE = REPO_ROOT / "warehouse" / "compass.duckdb"
API_KEY_ENV = "ANTHROPIC_API_KEY"
# nao's PostHog telemetry is on by default; the demo needs no hosted service but Anthropic.
_NAO_ENV = {"POSTHOG_DISABLED": "true"}


def nao(*args: str, project: Path = PROJECT_DIR, check: bool = True) -> int:
    """Run the nao CLI from this environment inside a nao project folder."""
    executable = Path(sys.executable).with_name("nao")
    return subprocess.run(
        [str(executable), *args], cwd=project, env={**os.environ, **_NAO_ENV}, check=check
    ).returncode


def sync(project: Path = PROJECT_DIR) -> None:
    """Regenerate the synced table metadata from the warehouse (no API key needed)."""
    nao("sync", project=project)
