"""`demo benchmark`'s checks before it spends anything. The run itself is never part of pytest."""

import subprocess

import pytest

from compass import benchmark, cli


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
