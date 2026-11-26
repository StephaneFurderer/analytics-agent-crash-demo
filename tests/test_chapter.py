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


def test_chapter_refuses_to_mix_local_changes_into_a_chapter(repo, tmp_path, capsys):
    (repo / "RULES.md").write_text("my own rule\n")
    head = git(repo, "rev-parse", "HEAD")

    assert cli.main(["chapter", "3", "--repo", str(repo), "--path", str(tmp_path / "w.duckdb")]) == 1

    assert git(repo, "rev-parse", "HEAD") == head
    assert (repo / "RULES.md").read_text() == "my own rule\n"
    assert "--force" in capsys.readouterr().err


def test_chapter_force_discards_local_context_files_and_leaves_a_clean_state(repo, tmp_path):
    (repo / "RULES.md").write_text("my own rule\n")
    (repo / "my_skill.md").write_text("an experiment\n")

    assert cli.main(["chapter", "3", "--force", "--repo", str(repo), "--path", str(tmp_path / "w.duckdb")]) == 0

    assert (repo / "RULES.md").read_text() == "Chapter 3 rules\n"
    assert not (repo / "my_skill.md").exists()
    assert git(repo, "status", "--porcelain") == ""


def test_chapter_without_a_tag_lists_the_available_chapters(repo, tmp_path, capsys):
    assert cli.main(["chapter", "5", "--repo", str(repo), "--path", str(tmp_path / "w.duckdb")]) == 1

    err = capsys.readouterr().err
    assert "chapter-5" in err and "chapter-3" in err
    assert not (tmp_path / "w.duckdb").exists()
