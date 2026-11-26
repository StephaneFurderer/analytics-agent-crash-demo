"""The committed Benchmark questions: well formed, and their reference SQL answers on a built warehouse.

Running the questions against the agent is the benchmark itself (`uv run demo benchmark`), never pytest.
"""

import re

import pytest

from compass import agent, benchmark

QUESTIONS = benchmark.questions()


def test_the_working_set_has_seed_questions_in_every_tier():
    working = [q for q in QUESTIONS.values() if q.set == "working"]
    assert {q.tier for q in working} == set(benchmark.TIERS)


@pytest.mark.parametrize("name", sorted(QUESTIONS))
def test_the_reference_sql_answers_from_the_metric_layer(name, full_con):
    question = QUESTIONS[name]
    assert question.sql, "a Benchmark question needs reference SQL"
    # Reference answers come from the Metric layer, not from the raw tables the agent may misread.
    relations = re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", question.sql, flags=re.IGNORECASE)
    assert relations and all(r.startswith("metric_") for r in relations), relations

    answer = full_con.sql(question.sql).df()

    assert len(answer) >= 1
    assert not answer.isna().any().any()


def test_the_agent_cannot_read_the_questions_or_their_reference_sql():
    ignored = (agent.PROJECT_DIR / ".naoignore").read_text().split()
    assert "tests/" in ignored
