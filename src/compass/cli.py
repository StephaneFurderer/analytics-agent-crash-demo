"""The `demo` command: `uv run demo <command>`.

Commands:
- `setup`: one-time setup after cloning (dependencies come from `uv`); builds the warehouse
- `reset`: rebuild the warehouse from scratch with the seeded generator
- `dashboard`: open the Legacy dashboard (Streamlit)
- `chapter N`: jump to a Chapter's tag and reset the warehouse and Context layer to it
- `chat`: open the Analytics agent (nao chat; needs an LLM key, see `secret check`)
- `benchmark`: run the Benchmark questions (nao test, 3 runs each; needs an LLM key, costs money)
- `judge`: score a Chapter's Exploratory questions run against the rubric with Claude (needs an LLM key)
- `secret check [NAME...]` / `secret run [--name NAME]... -- CMD`: the agents' secrets tool. Shows which LLM route
  and which source (shell, .env, Infisical) each secret comes from, or runs CMD with them injected. Never prints values.
- `report`: aggregate the archived benchmark results into the Accuracy matrix and a chart, plus Exploratory scores
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

from compass import agent, benchmark, chapters, exploratory, keys, warehouse


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

    commands.add_parser("chat", help="open the Analytics agent's nao chat (needs an LLM key)")

    bench = commands.add_parser("benchmark", help="run the Benchmark questions with nao test (costs API money)")
    bench.add_argument("--set", dest="set_name", choices=list(benchmark.SETS), default="working",
                       help="which questions to run (default: working)")
    bench.add_argument("--chapter", type=int,
                       help="the Chapter this run is for (default: the Chapter tag checked out)")
    bench.add_argument("--project", type=Path, default=agent.PROJECT_DIR, help=argparse.SUPPRESS)
    bench.add_argument("--results", type=Path, default=benchmark.RESULTS_DIR, help="where runs are archived")

    judge = commands.add_parser("judge", help="score a Chapter's Exploratory questions run with Claude as judge")
    judge.add_argument("--chapter", type=int,
                       help="the Chapter whose latest run to judge (default: the Chapter tag checked out)")
    judge.add_argument("--results", type=Path, default=benchmark.RESULTS_DIR, help="archived benchmark results")
    judge.add_argument("--questions", type=Path, default=benchmark.QUESTIONS_DIR, help="Benchmark questions")

    report = commands.add_parser("report", help="turn benchmark results into the Accuracy matrix and a chart")
    report.add_argument("--results", type=Path, default=benchmark.RESULTS_DIR, help="archived benchmark results")
    report.add_argument("--questions", type=Path, default=benchmark.QUESTIONS_DIR, help="Benchmark questions")
    report.add_argument("--out", type=Path, help="where to write the matrix and chart (default: --results)")

    secret = commands.add_parser("secret", help="check or inject secrets (shell, .env, Infisical) without printing them")
    secret_commands = secret.add_subparsers(dest="secret_command", required=True)
    check = secret_commands.add_parser("check", help="show the LLM route and where each secret comes from")
    check.add_argument("names", nargs="*", metavar="NAME", help="other secrets to look up")
    run = secret_commands.add_parser("run", help="run a command with the LLM route (and --name secrets) in its env")
    run.add_argument("--name", dest="names", action="append", default=[], metavar="NAME",
                     help="also inject this secret (repeatable)")
    run.add_argument("cmd", nargs=argparse.REMAINDER, help="-- the command to run")

    args = parser.parse_args(argv)
    if args.command == "secret":
        return _secret(args)
    if args.command == "benchmark":
        try:
            archived = benchmark.run(args.set_name, args.chapter, project=args.project, results_dir=args.results)
            print(f"\nRun archived: {archived}")
            if args.set_name == "exploratory":
                chapter = int(archived.parent.parent.name.removeprefix("ch"))
                print(f"Judged: {exploratory.judge_chapter(chapter, args.results, args.project / 'tests')}")
        except (agent.NotReady, benchmark.BenchmarkError) as problem:
            print(problem, file=sys.stderr)
            return 1
        print("Next: uv run demo report")
        return 0
    if args.command == "judge":
        try:
            chapter = benchmark.current_chapter() if args.chapter is None else args.chapter
            print(f"Judged: {exploratory.judge_chapter(chapter, args.results, args.questions)}")
        except (agent.NotReady, benchmark.BenchmarkError) as problem:
            print(problem, file=sys.stderr)
            return 1
        return 0
    if args.command == "report":
        try:
            print(benchmark.report(args.results, args.questions, args.out), end="")
        except benchmark.BenchmarkError as error:
            print(error, file=sys.stderr)
            return 1
        out = args.out or args.results
        print(f"\nWritten: {out / 'accuracy_matrix.md'}, {out / 'accuracy_matrix.png'}")
        return 0
    if args.command == "setup":
        return _setup(args.path)
    if args.command == "chat":
        try:
            return agent.chat()
        except agent.NotReady as problem:
            print(problem, file=sys.stderr)
            return 1
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


def _secret(args: argparse.Namespace) -> int:
    store = keys.Infisical.from_session()  # once: every lookup reuses the session
    try:
        route, no_key = keys.llm_route(infisical=store), ""
    except keys.NoKey as problem:
        route, no_key = None, str(problem)
    found = {name: keys.lookup(name, infisical=store) for name in args.names}
    if args.secret_command == "check":
        return _secret_check(store is not None, route, no_key, found)
    return _secret_run(args.cmd, route, no_key, found)


def _secret_check(has_session: bool, route: keys.Route | None, no_key: str,
                  found: dict[str, keys.Found | None]) -> int:
    print(f"Infisical: {'session found' if has_session else 'no session (optional: `infisical login`)'}")
    print(f"LLM: {route.describe()}" if route else f"LLM: none\n{no_key}")
    for name, secret in found.items():
        print(f"{name}: {secret.source if secret else 'missing'}")
    return 0 if route and all(found.values()) else 1


def _secret_run(cmd: list[str], route: keys.Route | None, no_key: str,
                found: dict[str, keys.Found | None]) -> int:
    cmd = cmd[1:] if cmd[:1] == ["--"] else cmd
    missing = [name for name, secret in found.items() if secret is None]
    if not cmd:
        problem = "Usage: demo secret run [--name NAME]... -- CMD"
    elif missing:
        problem = f"Missing secrets: {', '.join(missing)}"
    elif route is None and not found:
        problem = no_key
    else:
        injected = {name: secret.value for name, secret in found.items() if secret}
        return subprocess.call(cmd, env={**os.environ, **(route.nao_env() if route else {}), **injected})
    print(problem, file=sys.stderr)
    return 1


def _setup(path: Path) -> int:
    # `uv run` has already installed the pinned Python and the locked dependencies by the time this runs.
    print("Dependencies installed by uv.")
    warehouse.reset(path)
    print(f"Warehouse built from seed {warehouse.DEFAULT_SEED}: {path}")
    try:
        print(f"LLM key found: {keys.llm_route().describe()}. The Analytics agent and the benchmark can run.")
    except keys.NoKey as problem:
        print(f"Chapters 0-1 work without an LLM key; the Analytics agent (Chapter 2 on) needs one.\n{problem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
