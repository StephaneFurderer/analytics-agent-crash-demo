"""Exploratory questions: judged against their rubric by a (fake) Claude judge, reported apart from Accuracy.

The real judge calls the Anthropic API; pytest only ever uses fakes.
"""

import json

import pytest

from compass import benchmark, exploratory
from compass.cli import main as cli_main

from conftest import matrix_rows, nao_results, question, run_report


def exploratory_question(tests_dir, name, criteria):
    path = tests_dir / "exploratory" / f"{name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    rubric = "".join(f"  - id: {cid}\n    criterion: {text}\n" for cid, text in criteria.items())
    path.write_text(
        f"name: {name}\nprompt: What's driving {name}?\ntags: [set:exploratory]\n"
        f"assertions:\n  - type: tool_call\n    tool: execute_sql\nrubric:\n{rubric}"
    )


def exploratory_results(results_dir, chapter, answers, stamp="20261126_130000"):
    """A `nao test` results file for the Exploratory set; `answers` maps a question to each run's answer text."""
    path = results_dir / f"ch{chapter}" / "exploratory" / f"results_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    results = [
        {"name": name, "model": "anthropic:claude-opus-5-5", "passed": True, "message": "", "tokens": 1000,
         "cost": 0.05, "duration_ms": 1, "tool_call_count": 1, "error": None,
         "details": {"response_text": text}, "attempt": i}
        for name, texts in answers.items()
        for i, text in enumerate(texts, start=1)
    ]
    path.write_text(json.dumps({"timestamp": "2026-11-26T13:00:00", "results": results}))
    return path


class FakeJudge:
    """Marks a criterion met when the answer contains the keyword we give it, and records each prompt."""

    def __init__(self, keywords):
        self.keywords = keywords
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        answer = prompt.split("<answer>", 1)[1].split("</answer>", 1)[0]
        return json.dumps({"criteria": [
            {"id": cid, "met": keyword in answer, "reason": f"looked for {keyword!r}"}
            for cid, keyword in self.keywords.items()
        ]})


@pytest.fixture
def explored(tmp_path):
    tests_dir = tmp_path / "nao" / "tests"
    question(tests_dir, "working", "policy_count", "lookup", "working")
    exploratory_question(tests_dir, "underperformance", {
        "destination": "Finds the destination effect in Caribbean and Gulf Coast",
        "immature": "States that 2026 is immature",
    })
    return tmp_path, tests_dir, tmp_path / "benchmark-results"


def test_the_judge_sees_the_rubric_and_the_answer_and_its_prompt_and_scores_are_saved_with_the_run(explored):
    tmp_path, tests_dir, results_dir = explored
    run = exploratory_results(results_dir, 2, {"underperformance": ["Caribbean claims are up.", "No idea."]})
    judge = FakeJudge({"destination": "Caribbean", "immature": "immature"})

    saved = exploratory.judge_run(run, benchmark.questions(tests_dir), judge)

    assert saved.parent == run.parent
    assert len(judge.prompts) == 2
    assert "Finds the destination effect in Caribbean and Gulf Coast" in judge.prompts[0]
    assert "Caribbean claims are up." in judge.prompts[0]
    scores = json.loads(saved.read_text())
    assert scores["results_file"] == run.name
    first, second = scores["scores"]
    assert first["prompt"] == judge.prompts[0]
    assert {c["id"]: c["met"] for c in first["criteria"]} == {"destination": True, "immature": False}
    assert first["score"] == 0.5
    assert second["score"] == 0.0


def test_demo_report_shows_exploratory_scores_in_their_own_section_and_not_in_accuracy(explored):
    tmp_path, tests_dir, results_dir = explored
    nao_results(results_dir, 2, "working", {"policy_count": [True, True, True]})
    run = exploratory_results(results_dir, 2, {"underperformance": [
        "Caribbean is up and 2026 is immature.", "Caribbean is up.", "Prices are too low."]})
    exploratory.judge_run(run, benchmark.questions(tests_dir),
                          FakeJudge({"destination": "Caribbean", "immature": "immature"}))

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    markdown = (out / "accuracy_matrix.md").read_text()
    accuracy, exploratory_part = markdown.split("## Exploratory questions", 1)
    assert matrix_rows(accuracy, "Working set")[1]["All"] == ["100%"]
    assert "underperformance" not in accuracy
    header, rows = matrix_rows(markdown, "## Exploratory questions")
    assert header[1:] == ["Ch2"]
    assert rows["underperformance (score)"] == ["50%"]  # (2 + 1 + 0) of 2 criteria x 3 runs
    assert rows["underperformance: destination"] == ["2/3"]
    assert rows["underperformance: immature"] == ["1/3"]


def test_an_exploratory_run_not_yet_judged_is_reported_as_such(explored):
    tmp_path, tests_dir, results_dir = explored
    exploratory_results(results_dir, 3, {"underperformance": ["Caribbean."]})

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    exploratory_part = (out / "accuracy_matrix.md").read_text().split("## Exploratory questions", 1)[1]
    assert "Ch3: not judged yet" in exploratory_part


def test_demo_judge_scores_a_chapters_latest_exploratory_run(explored, monkeypatch):
    tmp_path, tests_dir, results_dir = explored
    exploratory_results(results_dir, 2, {"underperformance": ["old"]}, stamp="20261101_100000")
    latest = exploratory_results(results_dir, 2, {"underperformance": ["Caribbean, and 2026 is immature."]})
    # The Anthropic API is the boundary: stand a fake judge in for Claude, on a direct Anthropic route.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dummy-for-tests")
    monkeypatch.setattr(exploratory, "claude_judge",
                        lambda route: FakeJudge({"destination": "Caribbean", "immature": "immature"}))

    code = cli_main(["judge", "--chapter", "2", "--results", str(results_dir), "--questions", str(tests_dir)])

    assert code == 0
    scores = json.loads(exploratory.scores_path(latest).read_text())
    assert [s["score"] for s in scores["scores"]] == [1.0]


def test_demo_judge_asks_for_the_api_key(explored, monkeypatch, capsys):
    tmp_path, tests_dir, results_dir = explored
    exploratory_results(results_dir, 2, {"underperformance": ["Caribbean."]})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    code = cli_main(["judge", "--chapter", "2", "--results", str(results_dir), "--questions", str(tests_dir)])

    assert code == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert not list(results_dir.rglob("scores_*.json"))


def test_demo_judge_says_when_a_chapter_has_no_exploratory_run(explored, capsys):
    tmp_path, tests_dir, results_dir = explored

    code = cli_main(["judge", "--chapter", "4", "--results", str(results_dir), "--questions", str(tests_dir)])

    assert code == 1
    assert "No Exploratory questions run for Chapter 4" in capsys.readouterr().err
