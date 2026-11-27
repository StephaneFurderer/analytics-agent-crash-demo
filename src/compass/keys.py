"""Secrets for the demo, and the LLM route they open.

A secret is looked up in order:
1. the shell environment,
2. a `.env` file at the repo root (gitignored; the simplest option for followers),
3. Infisical: the `infra` project, `prod` environment, through your `infisical login` session (optional).

The first source holding the name wins, so a follower's own key always beats the shared vault. Nothing here
prints a secret's value: `describe()` and `demo secret check` show where a secret came from, never what it is.

The LLM route: an OpenRouter key (OPENROUTER_API_KEY / OPENROUTER_API_TOKEN) reaches Claude Opus 5.5 through
OpenRouter's Anthropic-compatible endpoint; an Anthropic key (ANTHROPIC_API_KEY / ANTHROPIC_API_TOKEN) reaches it directly. OpenRouter is tried
first within each source. There is no automatic retry: if OpenRouter fails, set COMPASS_LLM_PROVIDER=anthropic
(or openrouter) to force a provider.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
DOTENV = REPO_ROOT / ".env"

INFISICAL_PROJECT = "infra"
INFISICAL_ENVIRONMENT = "prod"
INFISICAL_API_URL = "https://app.infisical.com/api"
INFISICAL_CONFIG = Path.home() / ".infisical" / "infisical-config.json"

PROVIDER_ENV = "COMPASS_LLM_PROVIDER"


class NoKey(Exception):
    """No LLM key in any source; the message lists every way to provide one."""


class InfisicalError(Exception):
    """Infisical could not be reached, refused the session, or has no such project."""


class InfisicalNotFound(InfisicalError):
    """The project has no secret by that name."""


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...


@dataclass(frozen=True)
class Found:
    value: str
    source: str  # "shell", ".env" or "Infisical"


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


_UNSET = object()


def lookup(name: str, *, dotenv: Path | None = None, infisical: SecretStore | None | object = _UNSET) -> Found | None:
    """The secret `name` from the first source holding it, or None. Infisical defaults to your login session."""
    for source, get in _sources(dotenv, infisical):
        value = get(name)
        if value:
            return Found(value, source)
    return None


def llm_route(*, dotenv: Path | None = None, infisical: SecretStore | None | object = _UNSET) -> Route:
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
    values = read_dotenv(DOTENV if dotenv is None else dotenv)
    sources = [("shell", os.environ.get), (".env", values.get)]
    if infisical is _UNSET:
        sources.append(("Infisical", _session_vault()))
    elif infisical is not None:
        sources.append(("Infisical", _quiet(infisical)))
    return sources


def _session_vault() -> Callable[[str], str | None]:
    """Your login session's vault, opened only if a lookup gets this far (the shell and .env had nothing)."""
    store: list[SecretStore | None] = []

    def get(name: str) -> str | None:
        if not store:
            store.append(Infisical.from_session())
        return _quiet(store[0])(name) if store[0] else None
    return get


def _quiet(store: SecretStore) -> Callable[[str], str | None]:
    """An unreachable, refusing or confusing vault counts as empty: the other sources still work."""
    def get(name: str) -> str | None:
        try:
            return store.get(name)
        except InfisicalError:
            return None
    return get


def read_dotenv(path: Path) -> dict[str, str]:
    """KEY=VALUE lines of a .env file (comments, blank lines and `export ` allowed). Missing file: empty."""
    if not path.is_file():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.removeprefix("export ").split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[name.strip()] = value
    return values


GetJson = Callable[[str, str], dict]
"""GET a URL with a bearer token; return the JSON body. Raises InfisicalNotFound on 404, InfisicalError otherwise."""


def _get_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        kind = InfisicalNotFound if error.code == 404 else InfisicalError
        raise kind(f"Infisical answered {error.code} for {url.split('?')[0]}") from None
    except (urllib.error.URLError, TimeoutError) as error:
        raise InfisicalError(f"Infisical unreachable: {error}") from None


class Infisical:
    """Secrets of one Infisical project and environment, read through the REST API.

    `project` is matched against the names and slugs of the projects the token can see; set
    INFISICAL_PROJECT_ID to skip that lookup. INFISICAL_ENV overrides the environment slug.
    """

    def __init__(self, token: str, api_url: str = INFISICAL_API_URL, project: str = INFISICAL_PROJECT,
                 environment: str | None = None, get_json: GetJson = _get_json):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.project = project
        self.environment = environment or os.environ.get("INFISICAL_ENV", INFISICAL_ENVIRONMENT)
        self._get_json = get_json
        self._project_id = os.environ.get("INFISICAL_PROJECT_ID")

    def get(self, name: str) -> str | None:
        query = urllib.parse.urlencode(
            {"projectId": self.project_id(), "environment": self.environment, "secretPath": "/"})
        try:
            body = self._get_json(f"{self.api_url}/v4/secrets/{urllib.parse.quote(name)}?{query}", self.token)
        except InfisicalNotFound:
            return None
        try:
            return body["secret"]["secretValue"] or None
        except (KeyError, TypeError):
            raise InfisicalError(f"Unexpected Infisical reply for {name}") from None

    def project_id(self) -> str:
        if self._project_id is None:
            projects = self._get_json(f"{self.api_url}/v1/workspace", self.token).get("workspaces", [])
            matches = [p["id"] for p in projects if self.project in (p.get("name"), p.get("slug"))]
            if not matches:
                raise InfisicalError(f"No Infisical project named `{self.project}` is visible to this session.")
            self._project_id = matches[0]
        return self._project_id

    @classmethod
    def from_session(cls) -> Infisical | None:
        """The vault behind INFISICAL_TOKEN or your `infisical login` session; None when neither exists.

        Never starts a login: without a stored session this returns None and the other sources are used.
        """
        token = os.environ.get("INFISICAL_TOKEN") or _cli_session_token()
        if not token:
            return None
        return cls(token, api_url=os.environ.get("INFISICAL_API_URL") or _cli_api_url())


_JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")


def _cli_session_token() -> str | None:
    if shutil.which("infisical") is None or not INFISICAL_CONFIG.is_file():
        return None
    try:
        out = subprocess.run(["infisical", "user", "get", "token", "--plain", "--silent"], capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=20)
    except (subprocess.TimeoutExpired, OSError):
        return None
    match = _JWT.search(out.stdout)
    return match.group(0) if out.returncode == 0 and match else None


def _cli_api_url() -> str:
    """The API of the Infisical instance your active login profile uses, else Infisical Cloud (US)."""
    try:
        config = json.loads(INFISICAL_CONFIG.read_text())
    except (OSError, ValueError):
        config = {}
    profiles = {p.get("name"): p for p in config.get("profiles", []) if isinstance(p, dict)}
    domain = profiles.get(config.get("activeProfile"), {}).get("domain") or config.get("LoggedInUserDomain")
    url = (domain or INFISICAL_API_URL).rstrip("/")
    return url if url.endswith("/api") else f"{url}/api"
