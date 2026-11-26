"""`demo report`, driven through the CLI on fixture `nao test` result files (no agent, no API key)."""

import json

import pytest

from compass import cli


def question(tests_dir, folder, name, tier, set_name):
    path = tests_dir / folder / f"{name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: {name}\nprompt: What is {name}?\ntags: [tier:{tier}, set:{set_name}]\n"
        f"sql: SELECT 1 AS answer\n"
    )


def nao_results(results_dir, chapter, set_name, runs, stamp="20261126_120000"):
    """A results file shaped like `nao test`'s, archived where `demo benchmark` puts it.

    `runs` maps a question name to the pass/fail of each attempt.
    """
    path = results_dir / f"ch{chapter}" / set_name / f"results_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    results = [
        {"name": name, "model": "anthropic:claude-opus-5-5", "passed": passed, "message": "", "tokens": 1000,
         "cost": 0.05, "duration_ms": 1, "tool_call_count": 1, "error": None, "details": None, "attempt": i}
        for name, attempts in runs.items()
        for i, passed in enumerate(attempts, start=1)
    ]
    path.write_text(json.dumps({"timestamp": "2026-11-26T12:00:00", "results": results}))
    return path


def matrix_rows(markdown, heading):
    """The table under `heading` in the report, as {first cell: [other cells]}."""
    lines = markdown.split(heading, 1)[1].splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|"))
    table = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        if not set(line) <= set("|-: "):
            table.append([cell.strip() for cell in line.strip("|").split("|")])
    header, *rows = table
    return header, {row[0]: row[1:] for row in rows}


@pytest.fixture
def benchmark(tmp_path):
    tests_dir = tmp_path / "nao" / "tests"
    question(tests_dir, "working", "policy_count", "lookup", "working")
    question(tests_dir, "working", "paid_2025", "lookup", "working")
    question(tests_dir, "working", "loss_ratio", "definition", "working")
    question(tests_dir, "working", "ae_winter", "judgment", "working")
    question(tests_dir, "heldout", "ho_lookup", "lookup", "heldout")
    question(tests_dir, "heldout", "ho_definition", "definition", "heldout")
    return tmp_path, tests_dir, tmp_path / "benchmark-results"


def run_report(tmp_path, tests_dir, results_dir):
    out = tmp_path / "report"
    code = cli.main(["report", "--questions", str(tests_dir), "--results", str(results_dir), "--out", str(out)])
    return code, out


def test_a_question_is_correct_only_when_all_three_runs_pass(benchmark):
    tmp_path, tests_dir, results_dir = benchmark
    nao_results(results_dir, 2, "working", {
        "policy_count": [True, True, True],
        "paid_2025": [True, False, True],
        "loss_ratio": [False, False, False],
        "ae_winter": [True, True, True],
    })

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    header, rows = matrix_rows((out / "accuracy_matrix.md").read_text(), "Working set")
    assert header == ["Tier", "Ch2"]
    assert rows["Lookup"] == ["50%"]
    assert rows["Definition"] == ["0%"]
    assert rows["Judgment"] == ["100%"]
