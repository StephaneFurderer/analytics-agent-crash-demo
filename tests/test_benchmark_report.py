"""`demo report`, driven through the CLI on fixture `nao test` result files (no agent, no API key)."""

import pytest

from conftest import matrix_rows, nao_results, question, run_report


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


def test_held_out_results_are_reported_separately_and_never_mixed_into_the_working_set(benchmark):
    tmp_path, tests_dir, results_dir = benchmark
    all_pass = [True, True, True]
    nao_results(results_dir, 2, "working", {
        "policy_count": all_pass, "paid_2025": all_pass, "loss_ratio": all_pass, "ae_winter": all_pass,
        # A Held-out question that slipped into a Working-set run doesn't count for the Working set.
        "ho_lookup": [False, False, False],
    })
    nao_results(results_dir, 7, "heldout", {"ho_lookup": all_pass, "ho_definition": [True, True, False]})

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    markdown = (out / "accuracy_matrix.md").read_text()
    header, working = matrix_rows(markdown, "Working set")
    assert header == ["Tier", "Ch2"]
    assert working["Lookup"] == ["100%"]
    assert working["All"] == ["100%"]
    header, heldout = matrix_rows(markdown, "Held-out set")
    assert header == ["Tier", "Ch7"]
    assert heldout["Lookup"] == ["100%"]
    assert heldout["Definition"] == ["0%"]
    assert heldout["All"] == ["50%"]


def test_the_matrix_has_a_column_per_chapter_from_each_chapters_latest_run(benchmark):
    tmp_path, tests_dir, results_dir = benchmark
    all_pass, all_fail = [True, True, True], [False, False, False]
    nao_results(results_dir, 2, "working", {"policy_count": all_fail, "loss_ratio": all_fail}, "20261101_100000")
    nao_results(results_dir, 2, "working", {"policy_count": all_pass, "loss_ratio": all_fail}, "20261102_100000")
    nao_results(results_dir, 3, "working", {"policy_count": all_pass, "loss_ratio": all_pass})

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    header, rows = matrix_rows((out / "accuracy_matrix.md").read_text(), "Working set")
    assert header == ["Tier", "Ch2", "Ch3"]
    assert rows["Lookup"] == ["100%", "100%"]
    assert rows["Definition"] == ["0%", "100%"]
    assert rows["Judgment"] == ["–", "–"]  # not asked in either run


def test_the_report_writes_a_chart(benchmark):
    tmp_path, tests_dir, results_dir = benchmark
    nao_results(results_dir, 2, "working", {"policy_count": [True, True, True]})

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    assert (out / "accuracy_matrix.png").read_bytes().startswith(b"\x89PNG")


def test_a_question_with_fewer_than_three_runs_is_not_correct(benchmark):
    tmp_path, tests_dir, results_dir = benchmark
    nao_results(results_dir, 2, "working", {"policy_count": [True]})

    code, out = run_report(tmp_path, tests_dir, results_dir)

    assert code == 0
    markdown = (out / "accuracy_matrix.md").read_text()
    assert matrix_rows(markdown, "Working set")[1]["Lookup"] == ["0%"]
    assert "policy_count: only 1 of 3 runs" in markdown


def test_a_question_without_a_tier_is_rejected(benchmark, capsys):
    tmp_path, tests_dir, results_dir = benchmark
    (tests_dir / "working" / "untagged.yml").write_text("name: untagged\nprompt: Hi?\nsql: SELECT 1 AS a\n")

    code, _ = run_report(tmp_path, tests_dir, results_dir)

    assert code == 1
    assert "untagged.yml" in capsys.readouterr().err
