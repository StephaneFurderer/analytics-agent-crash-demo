"""Secrets for the demo, and the LLM route they open.

A secret is looked up in order:
1. the shell environment,
2. a `.env` file at the repo root (gitignored; the simplest option for followers),
3. Infisical: the `infra` project, `prod` environment, through your `infisical login` session (optional).

The first source holding the name wins, so a follower's own key always beats the shared vault. Nothing here
prints a secret's value: `describe()` and `demo secret check` show where a secret came from, never what it is.
The lookup itself is the shared one in `compass.vendor.secret` (see ADR 0006); this module adds the LLM route.

The LLM route: an OpenRouter key (OPENROUTER_API_KEY / OPENROUTER_API_TOKEN) reaches Claude Opus 5.5 through
OpenRouter's Anthropic-compatible endpoint; an Anthropic key (ANTHROPIC_API_KEY / ANTHROPIC_API_TOKEN) reaches it directly. OpenRouter is tried
first within each source. There is no automatic retry: if OpenRouter fails, set COMPASS_LLM_PROVIDER=anthropic
(or openrouter) to force a provider.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from compass.vendor import secret
from compass.vendor.secret import Found, Infisical, InfisicalError, InfisicalNotFound, read_dotenv

__all__ = ["DOTENV", "MODEL", "PROVIDERS", "Found", "Infisical", "InfisicalError", "InfisicalNotFound", "NoKey",
           "Provider", "Route", "llm_route", "lookup", "read_dotenv"]

REPO_ROOT = Path(__file__).resolve().parents[2]
DOTENV = REPO_ROOT / ".env"

INFISICAL_PROJECT = secret.DEFAULT_PROJECT
INFISICAL_ENVIRONMENT = secret.DEFAULT_ENVIRONMENT

PROVIDER_ENV = "COMPASS_LLM_PROVIDER"


class NoKey(Exception):
    """No LLM key in any source; the message lists every way to provide one."""


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...


@dataclass(frozen=True)
class Provider:
    """Who serves Claude for a key. Both speak the Anthropic Messages API, so nao's `anthropic` provider and the
    Anthropic SDK reach either one; only the base URL differs (nao's SDK wants it with `/v1`, the Python SDK without)."""

    name: str
    key_names: tuple[str, ...]
    nao_base_url: str
    sdk_base_url: str


MODEL = "claude-opus-5-5"
"""Claude Opus 5.5. OpenRouter's Anthropic endpoint takes the same id (it serves anthropic/claude-opus-5.5)."""

PROVIDERS = {
    "openrouter": Provider("openrouter", ("OPENROUTER_API_KEY", "OPENROUTER_API_TOKEN"),
                           "https://openrouter.ai/api/v1", "https://openrouter.ai/api"),
    "anthropic": Provider("anthropic", ("ANTHROPIC_API_KEY", "ANTHROPIC_API_TOKEN"),
                          "https://api.anthropic.com", "https://api.anthropic.com"),
}


@dataclass(frozen=True)
class Route:
    """How the Analytics agent and the judge reach Claude: who serves it, with which key, found where."""

    provider: str
    api_key: str
    source: str
    model: str = MODEL

    def nao_env(self) -> dict[str, str]:
        """The variables `nao/nao_config.yaml` reads its key and base URL from."""
        return {"COMPASS_LLM_API_KEY": self.api_key, "COMPASS_LLM_BASE_URL": PROVIDERS[self.provider].nao_base_url}

    def describe(self) -> str:
        return f"{self.model} via {self.provider}, key from {self.source}"

    def anthropic_client(self):
        """An Anthropic SDK client for this route."""
        import anthropic

        return anthropic.Anthropic(api_key=self.api_key, base_url=PROVIDERS[self.provider].sdk_base_url)


def lookup(name: str, *, dotenv: Path | None = None, infisical: SecretStore | None | object = secret.SESSION
           ) -> Found | None:
    """The secret `name` from the first source holding it, or None. Infisical defaults to your login session."""
    return secret.lookup(name, dotenv=DOTENV if dotenv is None else dotenv, infisical=infisical)


def llm_route(*, dotenv: Path | None = None, infisical: SecretStore | None | object = secret.SESSION) -> Route:
    """The LLM route the first key found opens. Raises NoKey when there is none."""
    forced = os.environ.get(PROVIDER_ENV)
    if forced and forced not in PROVIDERS:
        raise NoKey(f"{PROVIDER_ENV}={forced} is not one of: {', '.join(PROVIDERS)}.")
    providers = [PROVIDERS[forced]] if forced else list(PROVIDERS.values())
    for source, get in _sources(dotenv, infisical):
        for provider in providers:
            for name in provider.key_names:
                value = get(name)
                if value:
                    return Route(provider.name, value, source)
    raise NoKey(
        "No LLM key found. Provide one of:\n"
        "  - ANTHROPIC_API_KEY=sk-ant-... (direct to Anthropic) or OPENROUTER_API_KEY=sk-or-... (through OpenRouter),\n"
        "    exported in your shell or written to a .env file at the repo root (gitignored);\n"
        f"  - or run `infisical login` to use OPENROUTER_API_TOKEN / ANTHROPIC_API_TOKEN from the Infisical "
        f"`{INFISICAL_PROJECT}` project ({INFISICAL_ENVIRONMENT}).\n"
        "Check with `uv run demo secret check`."
    )


def _sources(dotenv: Path | None, infisical) -> list[tuple[str, Callable[[str], str | None]]]:
    return secret.sources(DOTENV if dotenv is None else dotenv, infisical)
