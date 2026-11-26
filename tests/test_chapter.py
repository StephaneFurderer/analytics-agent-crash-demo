"""`demo chapter N`, driven through the CLI against a throwaway git repo with test tags."""

import subprocess

import pytest

from compass import cli, metrics, warehouse


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A repo with Chapter 3 tagged on the first commit and later Context-layer work on top."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "RULES.md").write_text("Chapter 3 rules\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Rules and annotations")
    git(repo, "tag", "-a", "chapter-3", "-m", "Chapter 3: Rules and annotations\n\nAccuracy matrix: Lookup 90%")
    (repo / "RULES.md").write_text("Chapter 4 rules\n")
    (repo / "glossary.md").write_text("Business glossary\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Business glossary")
    return repo


def test_chapter_checks_out_the_tag_and_rebuilds_the_warehouse(repo, tmp_path, capsys):
    path = tmp_path / "warehouse" / "compass.duckdb"
    path.parent.mkdir()
    path.write_text("a warehouse someone experimented on")

    assert cli.main(["chapter", "3", "--repo", str(repo), "--path", str(path)]) == 0

    assert (repo / "RULES.md").read_text() == "Chapter 3 rules\n"
    assert not (repo / "glossary.md").exists()
    assert git(repo, "rev-parse", "HEAD") == git(repo, "rev-parse", "chapter-3^{commit}")
    assert git(repo, "status", "--porcelain") == ""
    con = warehouse.connect(path)
    assert metrics.query(con, ["booking_count"]).loc[0, "booking_count"] > 0
    con.close()
    assert "Accuracy matrix: Lookup 90%" in capsys.readouterr().out
