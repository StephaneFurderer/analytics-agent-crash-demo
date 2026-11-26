"""The Analytics agent's nao project, as committed (Chapter 2: synced table metadata only)."""

import re
import shutil
import subprocess

from nao_core.config import NaoConfig

from compass import agent, warehouse

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
    assert sorted(p.name for p in tables.iterdir()) == ["table=bookings", "table=destinations", "table=policies"]
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


def test_the_project_config_loads_with_a_key_from_the_environment():
    config = NaoConfig.load(agent.PROJECT_DIR, extra_env={"ANTHROPIC_API_KEY": DUMMY_KEY}, process_env=False)

    [database] = config.databases
    assert database.type == "duckdb"
    assert (agent.PROJECT_DIR / database.path).resolve() == agent.WAREHOUSE.resolve()
    [provider] = config.llm.providers
    assert provider.provider == "anthropic"
    assert provider.api_key == DUMMY_KEY
    assert [m.id for m in provider.models] == ["claude-opus-5-5"]


def test_the_committed_context_is_the_config_alone():
    # Chapter 2: no Rules, annotations, glossary, docs or prompts; the metadata comes from sync.
    assert committed_project_files() == ["nao_config.yaml"]


def test_no_api_key_is_committed():
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=agent.REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    key = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")
    offenders = [
        name for name in tracked
        if name and (agent.REPO_ROOT / name).is_file()
        and key.search((agent.REPO_ROOT / name).read_bytes().decode("utf-8", "ignore"))
    ]
    assert offenders == []
