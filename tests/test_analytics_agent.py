"""The Analytics agent's nao project, as committed (Chapter 2: synced table metadata only)."""

from nao_core.config import NaoConfig

from compass import agent

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
