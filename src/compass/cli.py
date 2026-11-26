"""The `demo` command: `uv run demo <command>`.

Commands:
- `reset`: rebuild the warehouse from scratch with the seeded generator
- `dashboard`: open the Legacy dashboard (Streamlit)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

from compass import warehouse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="demo", description="Compass Assistance analytics agent demo")
    commands = parser.add_subparsers(dest="command", required=True)

    reset = commands.add_parser("reset", help="rebuild the warehouse from scratch")
    reset.add_argument("--path", type=Path, default=warehouse.default_path(), help="warehouse file")
    reset.add_argument("--seed", type=int, default=warehouse.DEFAULT_SEED)

    dashboard = commands.add_parser("dashboard", help="open the Legacy dashboard")
    dashboard.add_argument("--path", type=Path, default=warehouse.default_path(), help="warehouse file")

    args = parser.parse_args(argv)
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
