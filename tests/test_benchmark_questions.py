"""The committed Benchmark questions: well formed, and their reference SQL answers on a built warehouse.

Running the questions against the agent is the benchmark itself (`uv run demo benchmark`), never pytest.
"""

import re

import pytest

from compass import agent, benchmark, metrics, warehouse
from compass.generator import generate_book

ALL_QUESTIONS = benchmark.questions()
QUESTIONS = {n: q for n, q in ALL_QUESTIONS.items() if q.set in benchmark.ACCURACY_SETS}
EXPLORATORY = {n: q for n, q in ALL_QUESTIONS.items() if q.set == "exploratory"}
WORKING = {n: q for n, q in QUESTIONS.items() if q.set == "working"}

# The actuarial traps the Working set must probe (ticket #12, user stories 48, 51 and 54). A question names the
# traps it targets with `trap:<id>` tags.
TRAPS = {
    "booking_vs_policy": "counting Policies where Bookings are meant, or the reverse",
    "pure_vs_commercial": "using the wrong premium basis",
    "purchase_vs_departure": "the wrong cohort: departure year instead of Underwriting year (purchase)",
    "written_vs_earned": "written premium where Earned premium is meant",
    "immature_year": "treating an immature Underwriting year as final (no IBNR)",
    "expert_judgment": "applying the actuary's assumptions (development, hurricane loading)",
    "geographic_ae": "A/E by destination, which the Legacy dashboard can't show",
}


def test_the_working_set_has_seed_questions_in_every_tier():
    working = [q for q in QUESTIONS.values() if q.set == "working"]
    assert {q.tier for q in working} == set(benchmark.TIERS)


def test_every_trap_is_probed_by_a_working_question():
    probed = {t for q in WORKING.values() for t in q.traps}
    assert probed == set(TRAPS), f"missing: {set(TRAPS) - probed}, unknown: {probed - set(TRAPS)}"


@pytest.fixture(scope="module")
def no_judgment_con(tmp_path_factory):
    """The seeded book with the Expert judgment taken out: no development (factors 1) and no Hurricane loading."""
    factors = metrics.standard_development_factors().assign(count_factor=1.0, amount_factor=1.0)
    loading = metrics.standard_hurricane_loading().assign(count_per_policy=0.0, amount_per_trip_cost=0.0)
    path = tmp_path_factory.mktemp("no_judgment") / "compass.duckdb"
    warehouse.write(path, development_factors=factors, hurricane_loading=loading,
                    **generate_book(warehouse.DEFAULT_SEED))
    con = warehouse.connect(path)
    yield con
    con.close()


@pytest.mark.parametrize("name", sorted(n for n, q in WORKING.items() if "expert_judgment" in q.traps))
def test_an_expert_judgment_answer_depends_on_the_assumptions(name, full_con, no_judgment_con):
    # Its reference answer uses the actuary's assumptions, so an agent that leaves them out is wrong.
    sql = QUESTIONS[name].sql
    with_judgment, without = full_con.sql(sql).df(), no_judgment_con.sql(sql).df()
    assert not with_judgment.round(2).equals(without.round(2))


def test_the_underperformance_rubric_checks_the_story_behind_the_numbers():
    rubric = {c.id for c in EXPLORATORY["exploratory_underperformance"].rubric}
    assert {"destination_effect", "immature_2026", "hurricane", "no_invented_cause"} <= rubric


@pytest.mark.parametrize("name", sorted(EXPLORATORY))
def test_an_exploratory_question_has_a_rubric_and_no_reference_answer(name):
    question = EXPLORATORY[name]
    assert question.sql is None
    assert question.rubric
    # The rubric sits under nao/tests/, which .naoignore hides from the agent.
    assert question.path.is_relative_to(agent.PROJECT_DIR / "tests")


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


@pytest.fixture(scope="module", params=[43, 44])
def other_seed_con(request, tmp_path_factory):
    """The same book drawn with another seed: what the noise alone could have given instead."""
    path = warehouse.reset(tmp_path_factory.mktemp(f"seed{request.param}") / "compass.duckdb", seed=request.param)
    con = warehouse.connect(path)
    yield con
    con.close()


@pytest.mark.parametrize("name", sorted(QUESTIONS))
def test_the_reference_answer_says_the_same_thing_under_another_seed(name, full_con, other_seed_con):
    # Which segment, region or A/E band a reference answer names must come from how the book was built (the
    # Drift, the hurricane), not from noise: otherwise "correct" flips between equally good answers.
    sql = QUESTIONS[name].sql

    def labels(con):
        answer = con.sql(sql).df()
        text = answer.select_dtypes(exclude="number")
        return sorted(map(tuple, text.astype(str).to_numpy())), len(answer)

    assert labels(other_seed_con) == labels(full_con)


def test_the_agent_cannot_read_the_questions_or_their_reference_sql():
    ignored = (agent.PROJECT_DIR / ".naoignore").read_text().split()
    assert "tests/" in ignored
