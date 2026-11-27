"""The benchmark: Benchmark questions as nao test definitions, and the Accuracy matrix.

A Benchmark question is a YAML file under `nao/tests/<set>/` (`working/` or `heldout/`):

    name: lookup_policy_count_2025          # unique; nao's results refer to questions by name
    prompt: How many policies were sold in underwriting year 2025?
    tags: [tier:lookup, set:working,        # one Tier, one set (matching the folder),
           trap:booking_vs_policy]          # and any actuarial traps the question probes
    sql: |                                  # reference answer, from the Metric layer
      SELECT count(*) AS policy_count FROM metric_policies WHERE underwriting_year = 2025

The warehouse file nao runs reference SQL on holds the base tables only (the Metric layer is applied per
connection, `metrics.connect`), so `demo benchmark` first stages the set (`stage`): each question is copied
under `nao/tests/_run/` with its reference answer computed through the Metric layer, written as literal rows.

`demo benchmark` runs one set with `nao test -k 3` and archives nao's results file under
`benchmark-results/ch<N>/<set>/`: the folder is what ties a run to its Chapter and set (nao's results
carry neither, nor the tags). `demo report` reads the latest file of each Chapter and set, joins the
results back to the questions by name, and counts a question correct only if all 3 runs passed.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from compass import agent, chapters

TIERS = {"lookup": "Lookup", "definition": "Definition", "judgment": "Judgment"}
SETS = {"working": "Working set", "heldout": "Held-out set", "exploratory": "Exploratory questions"}
ACCURACY_SETS = ("working", "heldout")  # objective sets; Exploratory questions are judged, never in Accuracy
RUNS = 3  # each question is asked this many times; correct only if every run is correct
QUESTIONS_DIR = agent.PROJECT_DIR / "tests"
RESULTS_DIR = agent.REPO_ROOT / "benchmark-results"
# Folder under the project's tests/ where `stage` writes the questions nao test runs (gitignored).
STAGED = "_run"


class BenchmarkError(Exception):
    """The questions or results can't be read; the message says which file and why."""


@dataclass(frozen=True)
class Criterion:
    """One line of an Exploratory question's rubric: what a good answer does, checked by the judge."""
    id: str
    criterion: str


@dataclass(frozen=True)
class Question:
    name: str
    tier: str | None  # None for Exploratory questions
    set: str
    prompt: str
    sql: str | None
    path: Path
    rubric: tuple[Criterion, ...] = ()
    traps: tuple[str, ...] = ()  # the actuarial traps it probes, from its `trap:<id>` tags


def questions(tests_dir: Path = QUESTIONS_DIR) -> dict[str, Question]:
    """Every Benchmark question under `tests_dir`, by name. Checks the tags and the folder."""
    found: dict[str, Question] = {}
    for path in sorted([*tests_dir.rglob("*.yml"), *tests_dir.rglob("*.yaml")]):
        relative = path.relative_to(tests_dir)
        if "outputs" in relative.parts or relative.parts[0] == STAGED:
            continue
        data = yaml.safe_load(path.read_text())
        name = data.get("name", path.stem)
        tags = dict(tag.split(":", 1) for tag in data.get("tags", []) if ":" in tag)
        tier, set_name = tags.get("tier"), tags.get("set")
        if set_name != "exploratory" and tier not in TIERS:
            raise BenchmarkError(f"{path}: needs a tier tag, one of {', '.join(f'tier:{t}' for t in TIERS)}")
        if set_name not in SETS or relative.parts[0] != set_name:
            raise BenchmarkError(f"{path}: needs the tag set:{relative.parts[0]} and to live in a set folder "
                                 f"({', '.join(SETS)})")
        rubric = _rubric(path, data.get("rubric")) if set_name == "exploratory" else ()
        if name in found:
            raise BenchmarkError(f"{path}: the name {name!r} is already used by {found[name].path}")
        traps = tuple(tag.split(":", 1)[1] for tag in data.get("tags", []) if tag.startswith("trap:"))
        found[name] = Question(name, tier, set_name, data["prompt"], data.get("sql"), path, rubric, traps)
    return found


def _rubric(path: Path, items) -> tuple[Criterion, ...]:
    """An Exploratory question's rubric: a non-empty list of {id, criterion} with unique ids."""
    if not items or not all(isinstance(i, dict) and i.get("id") and i.get("criterion") for i in items):
        raise BenchmarkError(f"{path}: an Exploratory question needs a rubric: a list of {{id, criterion}}")
    ids = [str(i["id"]) for i in items]
    if len(set(ids)) != len(ids):
        raise BenchmarkError(f"{path}: the rubric ids must be unique")
    return tuple(Criterion(str(i["id"]), " ".join(str(i["criterion"]).split())) for i in items)


# The benchmark's own chat server, on other ports than `demo chat` (5005/8005) so an open chat keeps running.
SERVER_PORT = 5105
FASTAPI_PORT = 8105
SERVER_START_SECONDS = 180


def current_chapter(repo: Path = agent.REPO_ROOT) -> int:
    """The Chapter a run belongs to: the one whose tag is checked out (after `demo chapter N`)."""
    found = chapters.at_head(repo)
    if len(found) == 1:
        return found[0]
    where = f"on the tags of Chapters {found}" if found else "not on a Chapter tag"
    raise BenchmarkError(f"The checked-out commit is {where}. Say which Chapter this run is for: --chapter N.")


def stage(set_name: str, project: Path, warehouse_path: Path) -> str:
    """Stage one set's questions for nao test; return the `nao test -s` selection that runs them.

    Each question is copied to `<project>/tests/_run/<set>/` with its reference SQL replaced by its answer
    (computed through the Metric layer on `warehouse_path`) as literal rows, so nao can check it on the
    bare warehouse file. Exploratory questions have no reference SQL and are copied as they are.
    """
    from compass import metrics

    staged_dir = project / "tests" / STAGED
    shutil.rmtree(staged_dir, ignore_errors=True)
    con = metrics.connect(warehouse_path)
    try:
        for question in questions(project / "tests").values():
            if question.set != set_name:
                continue
            data = yaml.safe_load(question.path.read_text())
            if question.sql:
                data["sql"] = literal_sql(con.sql(question.sql).df())
            target = staged_dir / question.path.relative_to(project / "tests")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    finally:
        con.close()
    return STAGED


def literal_sql(answer: pd.DataFrame) -> str:
    """A DuckDB query returning exactly `answer`'s rows and column names, from literals only."""
    columns = ", ".join('"' + str(c).replace('"', '""') + '"' for c in answer.columns)
    rows = [f"({', '.join(_literal(v) for v in row)})" for row in answer.itertuples(index=False)]
    if not rows:
        null_row = "(" + ", ".join("NULL" for _ in answer.columns) + ")"
        return f"SELECT * FROM (VALUES {null_row}) AS answer({columns}) WHERE false"
    return f"SELECT * FROM (VALUES {', '.join(rows)}) AS answer({columns})"


def _literal(value) -> str:
    if hasattr(value, "item") and not isinstance(value, pd.Timestamp):
        value = value.item()  # numpy scalar -> Python
    if value is None or (isinstance(value, float) and value != value):
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value!r}::DOUBLE"
    if isinstance(value, pd.Timestamp):
        if value == value.normalize():
            return f"DATE '{value.date().isoformat()}'"
        return f"TIMESTAMP '{value.isoformat(sep=' ')}'"
    if hasattr(value, "isoformat"):
        return f"DATE '{value.isoformat()}'"
    return "'" + str(value).replace("'", "''") + "'"


def run(set_name: str = "working", chapter: int | None = None, *, project: Path = agent.PROJECT_DIR,
        results_dir: Path = RESULTS_DIR) -> Path:
    """Run one set's Benchmark questions with `nao test -k 3`; return the archived results file.

    Starts a private `nao chat` server, signs up a throwaway local user on it, runs nao test against
    it, stops it, and copies nao's results file to `<results_dir>/ch<N>/<set>/`. Costs API money.
    """
    chapter = current_chapter() if chapter is None else chapter
    if not os.environ.get(agent.API_KEY_ENV):
        raise agent.NotReady(f"Set {agent.API_KEY_ENV} to your Anthropic API key; the benchmark calls the API.")
    asked = [q for q in questions(project / "tests").values() if q.set == set_name]
    if not asked:
        raise BenchmarkError(f"No {SETS[set_name]} questions in {project / 'tests' / set_name}.")
    warehouse = agent.warehouse_path(project)
    if not warehouse.exists():
        raise agent.NotReady(f"No warehouse at {warehouse}. Run `uv run demo reset` first.")

    agent.sync(project)
    selection = stage(set_name, project, warehouse)
    outputs = project / "tests" / "outputs"
    before = set(outputs.glob("results_*.json"))
    print(f"Benchmark: Chapter {chapter}, {SETS[set_name]}, {len(asked)} questions x {RUNS} runs.", flush=True)
    with _chat_server(project, outputs / "chat-server.log") as url:
        email, password = _local_user(url)
        # nao test exits 1 when any run fails; that's a result, not an error.
        agent.nao("test", "-k", str(RUNS), "-s", selection, project=project, check=False,
                  env={"BACKEND_URL": url, "NAO_USERNAME": email, "NAO_PASSWORD": password})
    new = sorted(set(outputs.glob("results_*.json")) - before)
    if not new:
        raise BenchmarkError(f"nao test wrote no results file in {outputs}; see its output above.")
    archived = results_dir / f"ch{chapter}" / set_name / new[-1].name
    archived.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(new[-1], archived)
    return archived


@contextlib.contextmanager
def _chat_server(project: Path, log_path: Path) -> Iterator[str]:
    """A `nao chat` server for the project, stopped on exit. Yields its URL."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"http://localhost:{SERVER_PORT}"
    env = {**os.environ, **agent.NAO_ENV,
           "BROWSER": "true",            # `nao chat` opens a browser; `true` is a no-op command
           "ENABLE_USER_SIGNUP": "true"}  # lets each run sign up its own local user (see _local_user)
    with log_path.open("w") as log:
        server = subprocess.Popen(
            [str(agent.executable()), "chat", "--port", str(SERVER_PORT), "--fastapi-port", str(FASTAPI_PORT)],
            cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            _wait_until_up(url, server, log_path)
            yield url
        finally:
            _stop(server)


def _wait_until_up(url: str, server: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + SERVER_START_SECONDS
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise BenchmarkError(f"nao chat stopped while starting; see {log_path}.")
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except urllib.error.HTTPError:
            return  # it answers
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    raise BenchmarkError(f"nao chat didn't answer on {url} within {SERVER_START_SECONDS} s; see {log_path}.")


def _stop(server: subprocess.Popen) -> None:
    # Ctrl-C to the whole process group: nao chat, its chat server and its FastAPI sidecar.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(server.pid, signal.SIGINT)
    try:
        server.wait(timeout=15)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(server.pid, signal.SIGKILL)
        server.wait()


def _local_user(url: str) -> tuple[str, str]:
    """Sign up a throwaway user on the local server; nao test logs in with it."""
    email = f"benchmark-{secrets.token_hex(4)}@compass.local"
    password = secrets.token_urlsafe(24)
    request = urllib.request.Request(
        f"{url}/api/auth/sign-up/email",
        data=json.dumps({"email": email, "password": password, "name": "Benchmark"}).encode(),
        headers={"Content-Type": "application/json", "Origin": url},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        raise BenchmarkError(f"Couldn't sign up a local user on {url}: {error.code} {error.read()[:300]!r}")
    return email, password


def _chapter_number(folder: Path) -> int | None:
    match = re.fullmatch(r"ch(\d+)", folder.name)
    return int(match.group(1)) if match else None


def latest_runs(results_dir: Path = RESULTS_DIR) -> dict[tuple[int, str], Path]:
    """The latest archived nao results file of each (Chapter, set)."""
    latest = {}
    for chapter_dir in sorted(results_dir.glob("ch*")):
        chapter = _chapter_number(chapter_dir)
        if chapter is None:
            continue
        for set_name in SETS:
            files = sorted((chapter_dir / set_name).glob("results_*.json"))
            if files:
                latest[(chapter, set_name)] = files[-1]
    return latest


def outcomes(results_dir: Path = RESULTS_DIR, tests_dir: Path = QUESTIONS_DIR) -> pd.DataFrame:
    """One row per (Chapter, set, question) that was run: its Tier, runs, runs passed and whether it is correct.

    A results file only counts for the questions of its own set, so a Held-out result can never
    land in Working-set Accuracy. Results for unknown questions are ignored.
    """
    known = questions(tests_dir)
    rows = []
    for (chapter, set_name), path in latest_runs(results_dir).items():
        if set_name not in ACCURACY_SETS:
            continue
        data = json.loads(path.read_text())
        runs: dict[str, list[bool]] = {}
        for result in data["results"]:
            question = known.get(result["name"])
            if question is not None and question.set == set_name:
                runs.setdefault(question.name, []).append(bool(result["passed"]))
        for name, passed in runs.items():
            rows.append({
                "chapter": chapter, "set": set_name, "question": name, "tier": known[name].tier,
                "runs": len(passed), "passed": sum(passed), "correct": len(passed) >= RUNS and all(passed),
            })
    return pd.DataFrame(rows, columns=["chapter", "set", "question", "tier", "runs", "passed", "correct"])


def accuracy_matrix(results: pd.DataFrame, set_name: str) -> pd.DataFrame:
    """Accuracy (share of questions correct) by Tier (rows, plus "All") and Chapter (columns) for one set."""
    of_set = results[results["set"] == set_name]
    chapters = sorted(of_set["chapter"].unique())
    matrix = pd.DataFrame(index=[*TIERS.values(), "All"], columns=[f"Ch{c}" for c in chapters], dtype=float)
    for chapter in chapters:
        in_chapter = of_set[of_set["chapter"] == chapter]
        for tier, label in TIERS.items():
            in_tier = in_chapter[in_chapter["tier"] == tier]
            if len(in_tier):
                matrix.loc[label, f"Ch{chapter}"] = in_tier["correct"].mean()
        matrix.loc["All", f"Ch{chapter}"] = in_chapter["correct"].mean()
    return matrix


def _markdown(matrix: pd.DataFrame) -> str:
    header = ["Tier", *matrix.columns]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for tier, row in matrix.iterrows():
        cells = ["–" if pd.isna(v) else f"{v:.0%}" for v in row]
        lines.append("| " + " | ".join([str(tier), *cells]) + " |")
    return "\n".join(lines)


def _run_summary(results_dir: Path) -> list[str]:
    lines = []
    for (chapter, set_name), path in sorted(latest_runs(results_dir).items()):
        data = json.loads(path.read_text())
        models = sorted({r["model"] for r in data["results"]})
        cost = sum(r.get("cost") or 0 for r in data["results"])
        errors = sum(1 for r in data["results"] if r.get("error"))
        note = f", {errors} run(s) errored" if errors else ""
        lines.append(f"- Ch{chapter} {SETS[set_name]}: {data.get('timestamp', '?')[:10]}, {', '.join(models)}, "
                     f"US${cost:.2f}, {len(data['results'])} runs{note} ({path.name})")
    return lines


def _chart(matrices: dict[str, pd.DataFrame], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    shown = {s: m for s, m in matrices.items() if len(m.columns)}
    fig, axes = plt.subplots(1, max(len(shown), 1), figsize=(6 * max(len(shown), 1), 4), squeeze=False)
    for ax, (set_name, matrix) in zip(axes[0], shown.items()):
        tiers = list(TIERS.values())
        width = 0.8 / len(matrix.columns)
        for i, chapter in enumerate(matrix.columns):
            values = matrix.loc[tiers, chapter].fillna(0).to_numpy() * 100
            ax.bar([t + i * width for t in range(len(tiers))], values, width, label=chapter)
        ax.set_xticks([t + width * (len(matrix.columns) - 1) / 2 for t in range(len(tiers))], tiers)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Accuracy (%), correct on all 3 runs")
        ax.set_title(SETS[set_name])
        ax.legend(title="Chapter")
    if not shown:
        axes[0][0].text(0.5, 0.5, "No benchmark results yet", ha="center", va="center")
        axes[0][0].axis("off")
    fig.suptitle("Accuracy matrix")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def report(results_dir: Path = RESULTS_DIR, tests_dir: Path = QUESTIONS_DIR, out_dir: Path | None = None) -> str:
    """Write the Accuracy matrix (`accuracy_matrix.md`) and its chart (`accuracy_matrix.png`) to `out_dir`.

    Returns the Markdown. The Working set and the Held-out set get separate tables; Exploratory
    questions get their own section with the judge's scores, outside the Accuracy matrix.
    """
    from compass import exploratory

    out_dir = out_dir or results_dir
    results = outcomes(results_dir, tests_dir)
    matrices = {s: accuracy_matrix(results, s) for s in ACCURACY_SETS}
    parts = ["# Accuracy matrix", "", f"Accuracy: share of Benchmark questions correct on all {RUNS} runs."]
    for set_name, matrix in matrices.items():
        parts += ["", f"## {SETS[set_name]}", ""]
        parts.append(_markdown(matrix) if len(matrix.columns) else "Not run yet.")
        short = results[(results["set"] == set_name) & (results["runs"] < RUNS)]
        for _, row in short.iterrows():
            parts.append(f"\nCh{row.chapter} {row.question}: only {row.runs} of {RUNS} runs, counted as incorrect.")
    parts += ["", "## Exploratory questions", "", *exploratory.report_lines(results_dir, tests_dir)]
    parts += ["", "## Runs", "", *(_run_summary(results_dir) or ["No benchmark results yet."])]
    markdown = "\n".join(parts) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "accuracy_matrix.md").write_text(markdown)
    _chart(matrices, out_dir / "accuracy_matrix.png")
    return markdown
