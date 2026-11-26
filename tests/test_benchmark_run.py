"""`demo benchmark`'s checks before it spends anything. The run itself is never part of pytest."""

import shutil
import subprocess

import pandas as pd
import pytest

from compass import agent, benchmark, cli, metrics, warehouse


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "RULES.md").write_text("Chapter 3 rules\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Rules")
    git(repo, "tag", "-a", "ch3-rules", "-m", "Chapter 3: Rules")
    return repo


def test_a_run_on_a_chapter_tag_belongs_to_that_chapter(repo):
    assert benchmark.current_chapter(repo) == 3


def test_a_run_between_chapter_tags_needs_the_chapter_named(repo):
    (repo / "glossary.md").write_text("work in progress\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Glossary")

    with pytest.raises(benchmark.BenchmarkError, match="--chapter"):
        benchmark.current_chapter(repo)


def test_demo_benchmark_asks_for_the_api_key_before_starting_anything(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert cli.main(["benchmark", "--chapter", "2"]) == 1

    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_demo_benchmark_refuses_a_set_without_questions(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-for-tests")

    assert cli.main(["benchmark", "--chapter", "2", "--set", "heldout", "--project", str(tmp_path)]) == 1

    assert "No Held-out set questions" in capsys.readouterr().err


def test_the_staged_reference_answers_are_the_metric_layers_answers_on_the_bare_warehouse(full_warehouse, tmp_path):
    # nao runs reference SQL on the warehouse file the agent sees, which has no Metric layer: `demo benchmark`
    # stages each question with its reference answer computed through the Metric layer, as literal rows.
    project = tmp_path / "nao"
    shutil.copytree(agent.PROJECT_DIR / "tests" / "working", project / "tests" / "working")

    selection = benchmark.stage("working", project, full_warehouse)

    original = benchmark.questions(project / "tests")
    staged = benchmark.questions(project / "tests" / selection)
    assert set(staged) == set(original)
    bare, layered = warehouse.connect(full_warehouse), metrics.connect(full_warehouse)
    try:
        for name, question in staged.items():
            assert question.set == "working" and question.tier == original[name].tier
            assert "metric_" not in question.sql
            # nao ignores row order.
            expected = _sorted(layered.sql(original[name].sql).df())
            got = _sorted(bare.sql(question.sql).df())
            pd.testing.assert_frame_equal(got, expected, check_dtype=False)
    finally:
        bare.close()
        layered.close()


def _sorted(frame):
    return frame.sort_values(list(frame.columns)).reset_index(drop=True)
