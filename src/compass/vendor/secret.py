#!/usr/bin/env python3
"""Agents' secrets tool: find a secret, or run a command with it, without ever printing its value.

    secret.py check NAME...                  where each NAME comes from (exit 1 if any is missing)
    secret.py run --name NAME... -- CMD ...  run CMD with each NAME in its environment

A secret is looked up in order, and the first source holding it wins:
1. the shell environment,
2. a `.env` file (default: `.env` in the current directory; set `--dotenv PATH`),
3. Infisical, through your `infisical login` session (or INFISICAL_TOKEN). Optional: without a session it is
   skipped and nothing prompts. Never starts a login.

Infisical settings, all optional: INFISICAL_PROJECT (name or slug, default `infra`) or INFISICAL_PROJECT_ID,
INFISICAL_ENV (default `prod`), INFISICAL_SECRET_PATH or `--path` (default `/`), INFISICAL_API_URL.

Standard library only, Python 3.9+. Generalised from analytics-agent-crash-demo's `src/compass/keys.py`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

DEFAULT_PROJECT = "infra"
DEFAULT_ENVIRONMENT = "prod"
DEFAULT_PATH = "/"
INFISICAL_API_URL = "https://app.infisical.com/api"
INFISICAL_CONFIG = Path.home() / ".infisical" / "infisical-config.json"


class InfisicalError(Exception):
    """Infisical could not be reached, refused the session, or has no such project."""


class InfisicalNotFound(InfisicalError):
    """The project has no secret by that name."""


@dataclass(frozen=True)
class Found:
    value: str
    source: str  # "shell", ".env" or "Infisical"

    def __repr__(self) -> str:  # never show the value, even in a traceback
        return f"Found(source={self.source!r})"


Get = Callable[[str], Optional[str]]
SESSION = object()
"""Default for `infisical`: open the vault behind your login session, and only if a lookup gets that far."""
_UNSET = SESSION


def lookup(name: str, *, dotenv: Path | None = None, infisical: object = _UNSET) -> Found | None:
    """The secret `name` from the first source holding it, or None. Infisical defaults to your login session."""
    for source, get in sources(dotenv, infisical):
        value = get(name)
        if value:
            return Found(value, source)
    return None


def sources(dotenv: Path | None, infisical: object = _UNSET) -> list[tuple[str, Get]]:
    """The sources in lookup order. `infisical`: a store with `get(name)`, None to skip it, or the session default."""
    values = read_dotenv(Path(".env") if dotenv is None else dotenv)
    found: list[tuple[str, Get]] = [("shell", os.environ.get), (".env", values.get)]
    if infisical is _UNSET:
        found.append(("Infisical", _session_vault()))
    elif infisical is not None:
        found.append(("Infisical", _quiet(infisical)))
    return found


def _session_vault(path: str | None = None) -> Get:
    """Your login session's vault, opened only if a lookup gets this far (the shell and .env had nothing)."""
    store: list = []

    def get(name: str) -> str | None:
        if not store:
            store.append(_open_session(path))
        return _quiet(store[0])(name) if store[0] else None
    return get


def _quiet(store) -> Get:
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
        if line.startswith("export "):
            line = line[len("export "):]
        name, value = line.split("=", 1)
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
    """Secrets of one Infisical project, environment and folder, read through the REST API."""

    def __init__(self, token: str, api_url: str = INFISICAL_API_URL, project: str | None = None,
                 environment: str | None = None, path: str | None = None, get_json: GetJson = _get_json):
        self.token = token
        self.api_url = api_url.rstrip("/")
        self.project = project or os.environ.get("INFISICAL_PROJECT", DEFAULT_PROJECT)
        self.environment = environment or os.environ.get("INFISICAL_ENV", DEFAULT_ENVIRONMENT)
        self.path = path or os.environ.get("INFISICAL_SECRET_PATH", DEFAULT_PATH)
        self._get_json = get_json
        self._project_id = os.environ.get("INFISICAL_PROJECT_ID")

    def __repr__(self) -> str:  # keep the token out of reprs
        return f"Infisical(project={self.project!r}, environment={self.environment!r}, path={self.path!r})"

    def get(self, name: str) -> str | None:
        query = urllib.parse.urlencode(
            {"projectId": self.project_id(), "environment": self.environment, "secretPath": self.path})
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
    def from_session(cls, path: str | None = None) -> Infisical | None:
        """The vault behind INFISICAL_TOKEN or your `infisical login` session; None when neither exists."""
        token = os.environ.get("INFISICAL_TOKEN") or _cli_session_token()
        if not token:
            return None
        return cls(token, api_url=os.environ.get("INFISICAL_API_URL") or _cli_api_url(), path=path)


def _open_session(path: str | None) -> Infisical | None:
    # Without a folder, call from_session() bare, so a caller's own from_session (or a test double) still fits.
    return Infisical.from_session(path=path) if path else Infisical.from_session()


_JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")


def _cli_session_token() -> str | None:
    if shutil.which("infisical") is None or not INFISICAL_CONFIG.is_file():
        return None
    try:
        out = subprocess.run(["infisical", "user", "get", "token", "--plain", "--silent"], capture_output=True,
                             text=True, stdin=subprocess.DEVNULL, timeout=20)
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


def main(argv: list[str] | None = None, *, infisical: object = _UNSET) -> int:
    parser = argparse.ArgumentParser(prog="secret", description="Find or inject secrets without printing them.")
    parser.add_argument("--dotenv", type=Path, help="the .env file to read (default: ./.env)")
    parser.add_argument("--path", help="Infisical folder, e.g. /newsfeed (default: INFISICAL_SECRET_PATH or /)")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="say where each secret comes from")
    check.add_argument("names", nargs="+", metavar="NAME")
    run = commands.add_parser("run", help="run a command with the secrets in its environment")
    run.add_argument("--name", dest="names", action="append", required=True, metavar="NAME",
                     help="a secret to inject (repeatable)")
    run.add_argument("cmd", nargs=argparse.REMAINDER, help="-- CMD ARGS")
    args = parser.parse_args(argv)

    if infisical is _UNSET:  # open the session once: every lookup reuses it
        infisical = _open_session(args.path)
        has_session = infisical is not None
    else:
        has_session = infisical is not None
    found = {name: lookup(name, dotenv=args.dotenv, infisical=infisical) for name in args.names}

    if args.command == "check":
        print(f"Infisical: {'session found' if has_session else 'no session (optional: run `infisical login`)'}")
        for name, secret in found.items():
            print(f"{name}: {secret.source if secret else 'missing'}")
        return 0 if all(found.values()) else 1

    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    missing = [name for name, secret in found.items() if secret is None]
    if not cmd:
        print("Usage: secret run --name NAME... -- CMD ARGS", file=sys.stderr)
        return 1
    if missing:
        print(f"Missing secrets: {', '.join(missing)}. See `secret check`.", file=sys.stderr)
        return 1
    return subprocess.call(cmd, env={**os.environ, **{name: secret.value for name, secret in found.items()}})


if __name__ == "__main__":
    raise SystemExit(main())
