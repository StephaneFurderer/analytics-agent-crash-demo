"""Chapter navigation: jump to a Chapter's annotated tag and reset to its state.

A Chapter is the annotated tag `chapter-N` (see docs/chapters.md). Jumping to it
1. checks out the tag (detached HEAD). The Context layer is versioned, so the
   checkout itself puts the Context layer in the chapter's state;
2. rebuilds the warehouse from the seed with the chapter's own code, in a fresh
   process, so a later chapter's generator or Metric layer never leaks back.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TAG_PREFIX = "chapter-"


class ChapterError(Exception):
    """A chapter jump that was refused; nothing was changed."""


def tag_name(chapter: int) -> str:
    return f"{TAG_PREFIX}{chapter}"


def jump(repo: Path, chapter: int, warehouse_path: Path, *, force: bool = False) -> str:
    """Check out chapter `chapter` in `repo`, rebuild the warehouse, return the tag annotation."""
    tag = tag_name(chapter)
    if _git(repo, "rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{tag}}", check=False).returncode != 0:
        available = ", ".join(available_chapters(repo)) or "none"
        raise ChapterError(f"No annotated tag {tag}. Chapters available: {available}.")

    dirty = _git(repo, "status", "--porcelain").stdout.strip()
    if dirty and not force:
        raise ChapterError(
            "You have local changes; a chapter jump would mix them with the chapter's Context layer.\n"
            f"{dirty}\n"
            "Commit or stash them, or re-run with --force to discard them."
        )
    if force:
        # Discard tracked changes and untracked files (e.g. your own context files);
        # ignored files such as .venv/ and the warehouse are kept.
        _git(repo, "reset", "-q", "--hard")
        _git(repo, "clean", "-q", "-fd")
    _git(repo, "checkout", "-q", "--detach", tag)

    _reset_warehouse(repo, warehouse_path)
    return _git(repo, "tag", "-l", "--format=%(contents)", tag).stdout.strip()


def available_chapters(repo: Path) -> list[str]:
    tags = _git(repo, "tag", "-l", f"{TAG_PREFIX}*", check=False).stdout.split()
    return sorted(tags, key=lambda t: int(t.removeprefix(TAG_PREFIX)) if t.removeprefix(TAG_PREFIX).isdigit() else 999)


def _reset_warehouse(repo: Path, warehouse_path: Path) -> None:
    # Run the checked-out chapter's code: its src/ comes first on the import path.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(repo / "src"), os.environ.get("PYTHONPATH", "")])}
    subprocess.run(
        [sys.executable, "-m", "compass.cli", "reset", "--path", str(warehouse_path.resolve())],
        cwd=repo,
        env=env,
        check=True,
    )


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise ChapterError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result
