"""The `demo` command: `uv run demo <command>`.

Commands:
- `setup`: one-time setup after cloning (dependencies come from `uv`); builds the warehouse
- `reset`: rebuild the warehouse from scratch with the seeded generator
- `dashboard`: open the Legacy dashboard (Streamlit)
- `chapter N`: jump to a Chapter's tag and reset the warehouse and Context layer to it
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

from compass import chapters, warehouse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo", description="Compass Assistance analytics agent demo")
    commands = parser.add_subparsers(dest="command", required=True)

    setup = commands.add_parser("setup", help="set up the demo after cloning")
    setup.add_argument("--path", type=Path, default=warehouse.default_path(), help="warehouse file")

    reset = commands.add_parser("reset", help="rebuild the warehouse from scratch")
    reset.add_argument("--path", type=Path, default=warehouse.default_path(), help="warehouse file")
    reset.add_argument("--seed", type=int, default=warehouse.DEFAULT_SEED)

    dashboard = commands.add_parser("dashboard", help="open the Legacy dashboard")
    dashboard.add_argument("--path", type=Path, default=warehouse.default_path(), help="warehouse file")

    chapter = commands.add_parser("chapter", help="jump to a Chapter and reset to its state")
    chapter.add_argument("number", type=int, help="chapter number (0-7)")
    chapter.add_argument("--force", action="store_true", help="discard local changes before jumping")
    chapter.add_argument("--repo", type=Path, default=Path.cwd(), help="repo root (default: current directory)")
    chapter.add_argument("--path", type=Path, help="warehouse file (default: <repo>/warehouse/compass.duckdb)")

    args = parser.parse_args(argv)
    if args.command == "setup":
        return _setup(args.path)
    if args.command == "reset":
        path = warehouse.reset(args.path, seed=args.seed)
        print(f"Warehouse rebuilt from seed {args.seed}: {path}")
        return 0
    if args.command == "dashboard":
        if not args.path.exists():
            print(f"No warehouse at {args.path}. Run `uv run demo reset` first.", file=sys.stderr)
            return 1
        app = resources.files("compass.dashboard").joinpath("app.py")
        env_path = str(args.path.resolve())
        return subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(app)],
            env={**os.environ, warehouse.PATH_ENV: env_path},
        )
    if args.command == "chapter":
        path = args.path or (
            Path(os.environ[warehouse.PATH_ENV]) if warehouse.PATH_ENV in os.environ else args.repo / warehouse.DEFAULT_PATH
        )
        try:
            tag, annotation = chapters.jump(args.repo, args.number, path, force=args.force)
        except chapters.ChapterError as error:
            print(error, file=sys.stderr)
            return 1
        print(f"Now on {tag}; warehouse rebuilt at {path}.\n\n{annotation}")
        return 0
    return 2


API_KEY_ENV = "ANTHROPIC_API_KEY"


def _setup(path: Path) -> int:
    # `uv run` has already installed the pinned Python and the locked dependencies by the time this runs.
    print("Dependencies installed by uv.")
    warehouse.reset(path)
    print(f"Warehouse built from seed {warehouse.DEFAULT_SEED}: {path}")
    if os.environ.get(API_KEY_ENV):
        print(f"{API_KEY_ENV} is set: the Analytics agent and the benchmark can run.")
    else:
        print(
            f"{API_KEY_ENV} is not set. Chapters 0-1 work without it; the Analytics agent (Chapter 2 on) "
            f"needs it. See the README."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
