"""The Analytics agent: a nao project over the local warehouse.

The nao project lives in `nao/` at the repo root. Its config reads the LLM provider, model and key
from the COMPASS_LLM_* variables of the route `keys.llm_route()` resolves, and points at the default
warehouse file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from compass import keys

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = REPO_ROOT / "nao"
# The warehouse file the nao config points at (relative to PROJECT_DIR in the config).
WAREHOUSE = REPO_ROOT / "warehouse" / "compass.duckdb"
API_KEY_ENV = "ANTHROPIC_API_KEY"  # one of the variables keys.llm_route() reads
# nao's PostHog telemetry is on by default; the demo needs no hosted service but the LLM provider.
NAO_ENV = {"POSTHOG_DISABLED": "true"}


def nao(*args: str, project: Path = PROJECT_DIR, check: bool = True, env: dict[str, str] | None = None) -> int:
    """Run the nao CLI from this environment inside a nao project folder (`env` adds variables)."""
    return subprocess.run(
        [str(executable()), *args], cwd=project, env={**os.environ, **NAO_ENV, **(env or {})}, check=check
    ).returncode


def executable() -> Path:
    """The nao CLI installed in this environment."""
    return Path(sys.executable).with_name("nao")


class NotReady(Exception):
    """The agent can't start yet; the message says what to do."""


def llm_route() -> keys.Route:
    """The route to Claude from the first key found (shell, .env, Infisical). Raises NotReady without one."""
    try:
        return keys.llm_route()
    except keys.NoKey as problem:
        raise NotReady(str(problem)) from None


def sync(project: Path = PROJECT_DIR) -> None:
    """Regenerate the synced table metadata from the warehouse (no API key needed)."""
    nao("sync", project=project)


def warehouse_path(project: Path = PROJECT_DIR) -> Path:
    """The DuckDB file the project's nao config points at."""
    from nao_core.config import NaoConfig  # heavy import, only when needed

    [database] = NaoConfig.load(project, drop_invalid_optional_sections=True).databases
    return (project / database.path).resolve()


def chat(project: Path = PROJECT_DIR) -> int:
    """Sync the table metadata, then open the nao chat (web UI) on the warehouse.

    Blocks until the chat server stops (Ctrl-C). Raises NotReady without an LLM key or a warehouse.
    """
    route = llm_route()
    path = warehouse_path(project)
    if not path.exists():
        raise NotReady(f"No warehouse at {path}. Run `uv run demo reset` first.")
    sync(project)
    print(f"Analytics agent: {route.describe()}", flush=True)
    return nao("chat", project=project, check=False, env=route.nao_env())
