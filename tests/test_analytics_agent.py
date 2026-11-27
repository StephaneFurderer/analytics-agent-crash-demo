"""The Analytics agent's nao project, as committed (Chapter 2: synced table metadata only)."""

import re
import shutil
import subprocess

import pytest
from nao_core.config import NaoConfig

from compass import agent, cli, keys, warehouse

from conftest import BOOKINGS, DESTINATIONS, POLICIES


def committed_project_files():
    """Paths (relative to the nao project) of the files git tracks in it."""
    out = subprocess.run(
        ["git", "ls-files", "--", "."], cwd=agent.PROJECT_DIR, capture_output=True, text=True, check=True
    ).stdout
    return sorted(out.split())


def manual_body(text):
    """A nao Markdown file without its front matter."""
    return text.split("---", 2)[2].strip() if text.startswith("---") else text.strip()


def test_sync_writes_only_table_metadata_for_the_raw_schema(tmp_path):
    project = tmp_path / "nao"
    for name in committed_project_files():
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(agent.PROJECT_DIR / name, project / name)
    warehouse.write(tmp_path / "warehouse" / "compass.duckdb",
                    destinations=DESTINATIONS, bookings=BOOKINGS, policies=POLICIES)
    config_before = (project / "nao_config.yaml").read_text()

    agent.sync(project)

    tables = project / "databases" / "type=duckdb" / "database=compass" / "schema=main"
    # Every base table, and none of the Metric layer's metric_* views or catalogue.
    assert sorted(p.name for p in tables.iterdir()) == sorted(f"table={t}" for t in warehouse.TABLES)
    for table in tables.iterdir():
        assert sorted(p.name for p in table.iterdir()) == ["annotations.md", "columns.md", "preview.md"]
        assert manual_body((table / "annotations.md").read_text()) == ""
        assert "_No description available._" in (table / "columns.md").read_text()
    # No Rules, docs, semantics or prompts: only the config and what sync generated.
    assert sorted(p.name for p in project.iterdir()) == sorted(
        {".meta", "databases", *(name.split("/")[0] for name in committed_project_files())}
    )
    assert (project / "nao_config.yaml").read_text() == config_before

DUMMY_KEY = "sk-ant-dummy-for-tests"


@pytest.mark.parametrize("route", [
    keys.Route("anthropic", DUMMY_KEY, "shell"),
    keys.Route("openrouter", "sk-or-dummy-for-tests", "Infisical"),
], ids=["anthropic", "openrouter"])
def test_the_project_config_loads_with_the_route_the_key_opens(route):
    config = NaoConfig.load(agent.PROJECT_DIR, extra_env=route.nao_env(), process_env=False)

    [database] = config.databases
    assert database.type == "duckdb"
    assert (agent.PROJECT_DIR / database.path).resolve() == agent.WAREHOUSE.resolve()
    [provider] = config.llm.providers
    # Literal provider and model: nao's server reads them raw. Only the key and base URL follow the route.
    assert provider.provider == "anthropic"
    assert provider.api_key == route.api_key
    assert provider.base_url == route.nao_env()["COMPASS_LLM_BASE_URL"]
    assert [m.id for m in provider.models] == ["claude-opus-5-5"]
    # The benchmark asks each question 3 times, with the agent's model.
    assert config.test.k == 3
    assert config.test.models == ["anthropic:claude-opus-5-5"]


def test_the_committed_context_is_the_config_alone():
    # Chapter 2: no Rules, annotations, glossary, docs or prompts; the metadata comes from sync.
    # The benchmark's questions (tests/) are committed too, but hidden from the agent by .naoignore.
    context = [name for name in committed_project_files() if not name.startswith("tests/")]
    assert context == [".naoignore", "nao_config.yaml"]


def test_no_api_key_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=agent.REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    key = re.compile(r"sk-(ant|or)-[A-Za-z0-9_-]{20,}")
    offenders = [
        name for name in tracked
        if name and (agent.REPO_ROOT / name).is_file()
        and key.search((agent.REPO_ROOT / name).read_bytes().decode("utf-8", "ignore"))
    ]
    assert offenders == []


def test_demo_chat_asks_for_the_api_key_when_it_is_missing(monkeypatch, capsys):
    monkeypatch.delenv(agent.API_KEY_ENV, raising=False)

    assert cli.main(["chat"]) == 1
    assert agent.API_KEY_ENV in capsys.readouterr().err


def test_chat_asks_for_a_reset_when_there_is_no_warehouse(tmp_path, monkeypatch):
    monkeypatch.setenv(agent.API_KEY_ENV, DUMMY_KEY)
    project = tmp_path / "nao"
    project.mkdir()
    shutil.copy(agent.PROJECT_DIR / "nao_config.yaml", project)

    with pytest.raises(agent.NotReady, match="demo reset"):
        agent.chat(project)


def test_nao_chat_keeps_its_app_database_outside_the_agents_project(tmp_path):
    # nao's default app database sits in the virtualenv and admits only its first user ever to the project.
    env = agent.app_db_env(tmp_path / "app" / "chat.sqlite")

    assert env == {"DB_URI": f"sqlite:{(tmp_path / 'app' / 'chat.sqlite').resolve()}"}
    assert (tmp_path / "app").is_dir()
    assert not agent.CHAT_DB.resolve().is_relative_to(agent.PROJECT_DIR.resolve())
