"""Chapter navigation: jump to a Chapter's annotated tag and reset to its state.

A Chapter is the single annotated tag `chN-<slug>`, e.g. `ch3-rules` (see docs/chapters.md). Jumping to it
1. checks out the tag (detached HEAD). The Context layer is versioned, so the
   checkout itself puts the Context layer in the chapter's state;
2. rebuilds the warehouse from the seed with the chapter's own code, in a fresh
   process, so a later chapter's generator or Metric layer never leaks back.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path



class ChapterError(Exception):
    """A chapter jump that was refused; nothing was changed."""


def pattern(chapter: int) -> str:
    return f"ch{chapter}-*"


def find_tag(repo: Path, chapter: int) -> str:
    """The one annotated tag for `chapter`; refuse if there are none or several."""
    matches = _annotated_tags(repo, pattern(chapter))
    if not matches:
        available = ", ".join(_annotated_tags(repo, "ch*-*")) or "none"
        raise ChapterError(f"No annotated tag matching {pattern(chapter)}. Chapter tags available: {available}.")
    if len(matches) > 1:
        raise ChapterError(
            f"Several annotated tags match {pattern(chapter)}: {', '.join(matches)}. "
            "There must be exactly one per Chapter (see docs/chapters.md)."
        )
    return matches[0]


def jump(repo: Path, chapter: int, warehouse_path: Path, *, force: bool = False) -> tuple[str, str]:
    """Check out chapter `chapter` in `repo`, rebuild the warehouse, return (tag, annotation)."""
    tag = find_tag(repo, chapter)

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
    return tag, _git(repo, "tag", "-l", "--format=%(contents)", tag).stdout.strip()


def at_head(repo: Path) -> list[int]:
    """The Chapters whose annotated tag points at the checked-out commit."""
    tags = _annotated_tags(repo, "ch*-*", "--points-at", "HEAD")
    return sorted({int(m.group(1)) for t in tags if (m := re.fullmatch(r"ch(\d+)-.+", t))})


def _annotated_tags(repo: Path, glob: str, *options: str) -> list[str]:
    refs = _git(repo, "for-each-ref", *options, "--format=%(objecttype) %(refname:short)", f"refs/tags/{glob}").stdout
    return sorted(name for kind, name in (line.split(" ", 1) for line in refs.splitlines()) if kind == "tag")


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
