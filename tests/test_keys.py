"""Where the demo finds its secrets (shell, .env, Infisical) and which LLM route a key opens."""

import pytest

from compass import cli, keys


class FakeInfisical:
    """Stands in for the Infisical service: a project's secrets in one environment."""

    def __init__(self, secrets):
        self.secrets = secrets
        self.asked = []

    def get(self, name):
        self.asked.append(name)
        return self.secrets.get(name)


def test_a_shell_variable_wins_over_dotenv_and_infisical(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=from-dotenv\n")
    infisical = FakeInfisical({"ANTHROPIC_API_KEY": "from-infisical"})

    found = keys.lookup("ANTHROPIC_API_KEY", dotenv=dotenv, infisical=infisical)

    assert (found.value, found.source) == ("from-shell", "shell")
    assert infisical.asked == []


def test_a_dotenv_file_is_read_without_infisical(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text('# my key\nexport OTHER=1\nOPENROUTER_API_KEY="sk-or-quoted"\n')

    found = keys.lookup("OPENROUTER_API_KEY", dotenv=dotenv, infisical=None)

    assert (found.value, found.source) == ("sk-or-quoted", ".env")


def test_infisical_is_the_last_resort(tmp_path):
    infisical = FakeInfisical({"OPENROUTER_API_TOKEN": "sk-or-vault"})

    found = keys.lookup("OPENROUTER_API_TOKEN", dotenv=tmp_path / ".env", infisical=infisical)

    assert (found.value, found.source) == ("sk-or-vault", "Infisical")


def test_a_missing_secret_is_none(tmp_path):
    assert keys.lookup("NOPE", dotenv=tmp_path / ".env", infisical=FakeInfisical({})) is None


def test_the_infisical_tokens_route_through_openrouter_first(tmp_path):
    infisical = FakeInfisical({"OPENROUTER_API_TOKEN": "sk-or-vault", "ANTHROPIC_API_TOKEN": "sk-ant-vault"})

    route = keys.llm_route(dotenv=tmp_path / ".env", infisical=infisical)

    assert (route.provider, route.model, route.api_key) == ("openrouter", "anthropic/claude-opus-5.5", "sk-or-vault")
    assert route.source == "Infisical"


def test_a_followers_own_anthropic_key_beats_the_shared_vault(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=sk-ant-mine\n")
    infisical = FakeInfisical({"OPENROUTER_API_TOKEN": "sk-or-vault"})

    route = keys.llm_route(dotenv=dotenv, infisical=infisical)

    assert (route.provider, route.model, route.api_key, route.source) == (
        "anthropic", "claude-opus-5-5", "sk-ant-mine", ".env")


def test_the_provider_can_be_forced_when_openrouter_does_not_work(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_LLM_PROVIDER", "anthropic")
    infisical = FakeInfisical({"OPENROUTER_API_TOKEN": "sk-or-vault", "ANTHROPIC_API_TOKEN": "sk-ant-vault"})

    route = keys.llm_route(dotenv=tmp_path / ".env", infisical=infisical)

    assert (route.provider, route.api_key) == ("anthropic", "sk-ant-vault")


def test_no_key_anywhere_says_every_way_to_provide_one(tmp_path):
    with pytest.raises(keys.NoKey) as problem:
        keys.llm_route(dotenv=tmp_path / ".env", infisical=FakeInfisical({}))

    message = str(problem.value)
    for hint in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", ".env", "infisical login"):
        assert hint in message


def test_a_route_hands_nao_its_provider_model_and_key():
    route = keys.Route("openrouter", "anthropic/claude-opus-5.5", "sk-or-x", "Infisical")

    assert route.nao_env() == {"COMPASS_LLM_PROVIDER": "openrouter",
                               "COMPASS_LLM_MODEL": "anthropic/claude-opus-5.5",
                               "COMPASS_LLM_API_KEY": "sk-or-x"}
    assert "sk-or-x" not in route.describe()


class FakeApi:
    """The Infisical REST API: answers GETs from a table of path -> JSON, recording the requests."""

    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def __call__(self, url, token):
        self.requests.append((url, token))
        for prefix, body in self.responses.items():
            if prefix in url:
                return body
        raise keys.InfisicalNotFound(f"404 for {url}")


def test_infisical_finds_the_infra_project_by_name_and_reads_prod():
    api = FakeApi({
        "/api/v1/workspace": {"workspaces": [{"id": "p-other", "name": "web", "slug": "web"},
                                             {"id": "p-infra", "name": "infra", "slug": "infra-x1"}]},
        "/api/v4/secrets/OPENROUTER_API_TOKEN": {"secret": {"secretKey": "OPENROUTER_API_TOKEN",
                                                            "secretValue": "sk-or-vault"}},
    })
    infisical = keys.Infisical(token="jwt", api_url="https://vault.example/api", get_json=api)

    assert infisical.get("OPENROUTER_API_TOKEN") == "sk-or-vault"

    url, token = api.requests[-1]
    assert token == "jwt"
    assert url.startswith("https://vault.example/api/v4/secrets/OPENROUTER_API_TOKEN?")
    assert "projectId=p-infra" in url and "environment=prod" in url and "secretPath=%2F" in url


def test_infisical_reports_a_secret_it_does_not_hold_as_missing():
    api = FakeApi({"/api/v1/workspace": {"workspaces": [{"id": "p-infra", "name": "infra", "slug": "infra"}]}})
    infisical = keys.Infisical(token="jwt", api_url="https://vault.example/api", get_json=api)

    assert infisical.get("ANTHROPIC_API_TOKEN") is None


def test_infisical_without_the_project_says_so():
    api = FakeApi({"/api/v1/workspace": {"workspaces": [{"id": "p-web", "name": "web", "slug": "web"}]}})
    infisical = keys.Infisical(token="jwt", api_url="https://vault.example/api", get_json=api)

    with pytest.raises(keys.InfisicalError, match="infra"):
        infisical.get("OPENROUTER_API_TOKEN")


# `demo secret`: the agents' tool. It reports where secrets come from and injects them into a command,
# and never prints a value.

CHILD = ["python3", "-c", "import os, sys; sys.exit(0 if os.environ.get('{name}') == '{value}' else 3)"]


def child(name, value):
    return [part.format(name=name, value=value) for part in CHILD]


def test_secret_check_names_the_llm_route_and_sources_without_values(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value")

    assert cli.main(["secret", "check", "ANTHROPIC_API_KEY", "NOT_THERE"]) == 1

    out = capsys.readouterr().out
    assert "anthropic (claude-opus-5-5), key from shell" in out
    assert "ANTHROPIC_API_KEY: shell" in out
    assert "NOT_THERE: missing" in out
    assert "sk-ant-secret-value" not in out


def test_secret_check_without_any_llm_key_explains_the_options(capsys):
    assert cli.main(["secret", "check"]) == 1

    assert "infisical login" in capsys.readouterr().out


def test_secret_run_injects_the_llm_route_into_the_command(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(keys, "DOTENV", tmp_path / ".env")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk-or-from-dotenv\n")

    assert cli.main(["secret", "run", "--", *child("COMPASS_LLM_API_KEY", "sk-or-from-dotenv")]) == 0
    assert cli.main(["secret", "run", "--", *child("COMPASS_LLM_PROVIDER", "openrouter")]) == 0
    assert "sk-or-from-dotenv" not in capsys.readouterr().out


def test_secret_run_injects_named_secrets_and_passes_the_exit_code(monkeypatch):
    infisical = FakeInfisical({"DEPLOY_TOKEN": "t-123"})
    monkeypatch.setattr(keys.Infisical, "from_session", classmethod(lambda cls: infisical))

    assert cli.main(["secret", "run", "--name", "DEPLOY_TOKEN", "--", *child("DEPLOY_TOKEN", "t-123")]) == 0
    assert cli.main(["secret", "run", "--name", "DEPLOY_TOKEN", "--", *child("DEPLOY_TOKEN", "other")]) == 3


def test_secret_run_refuses_a_missing_named_secret(capsys):
    assert cli.main(["secret", "run", "--name", "NOT_THERE", "--", "true"]) == 1

    assert "NOT_THERE" in capsys.readouterr().err


def test_infisical_is_not_opened_when_the_shell_has_the_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-mine")
    opened = []
    monkeypatch.setattr(keys.Infisical, "from_session", classmethod(lambda cls: opened.append(1)))

    assert keys.llm_route().source == "shell"
    assert opened == []


def test_an_unexpected_infisical_reply_counts_as_missing(tmp_path):
    api = FakeApi({"/api/v1/workspace": {"workspaces": [{"id": "p", "name": "infra", "slug": "infra"}]},
                   "/api/v4/secrets/": {"error": "something else"}})
    infisical = keys.Infisical(token="jwt", api_url="https://vault.example/api", get_json=api)

    assert keys.lookup("OPENROUTER_API_TOKEN", dotenv=tmp_path / ".env", infisical=infisical) is None
