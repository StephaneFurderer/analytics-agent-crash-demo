"""Exploratory questions: open business questions scored against a published rubric, with Claude as judge.

An Exploratory question is a YAML file under `nao/tests/exploratory/` with `tags: [set:exploratory]`,
no `sql` (there's no single correct number) and a `rubric` (nao ignores that key). The rubric lives
under `nao/tests/`, which `nao/.naoignore` hides from the Analytics agent, so it never sees it.

`demo benchmark --set exploratory` runs the questions with nao test like any other set, then
`judge_run` asks the judge to check each answer against its question's rubric. The judge's prompt,
raw reply and per-criterion verdicts are saved next to the run as `scores_<stamp>.json`.
Scores are reported in their own section of `demo report`, never in the Accuracy matrix.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path

from compass import agent
from compass.benchmark import BenchmarkError, Question

JUDGE_MODEL = "claude-opus-5-5"

Judge = Callable[[str], str]
"""Takes the judge prompt, returns the judge's reply (JSON, see `judge_prompt`)."""


def claude_judge(model: str = JUDGE_MODEL) -> Judge:
    """The real judge: Claude through the Anthropic API. Needs ANTHROPIC_API_KEY; costs money."""
    if not os.environ.get(agent.API_KEY_ENV):
        raise agent.NotReady(f"Set {agent.API_KEY_ENV} to your Anthropic API key; the judge calls the API.")
    import anthropic

    client = anthropic.Anthropic()

    def judge(prompt: str) -> str:
        message = client.messages.create(model=model, max_tokens=2000,
                                         messages=[{"role": "user", "content": prompt}])
        return "".join(block.text for block in message.content if block.type == "text")

    return judge


def judge_prompt(question: Question, answer: str) -> str:
    criteria = "\n".join(f"- {c.id}: {c.criterion}" for c in question.rubric)
    ids = ", ".join(c.id for c in question.rubric)
    return f"""You are grading an analytics agent's answer to an open business question from a travel \
insurer's management. Judge only what the answer itself says, against each rubric criterion. A criterion \
is met only if the answer clearly does what it describes; vague or hedged mentions do not count.

<question>
{question.prompt}
</question>

<rubric>
{criteria}
</rubric>

<answer>
{answer}
</answer>

Reply with JSON only, no other text, one entry per criterion id ({ids}):
{{"criteria": [{{"id": "<criterion id>", "met": true or false, "reason": "<one sentence>"}}]}}"""


def _verdicts(question: Question, reply: str) -> list[dict]:
    """The judge's verdict per rubric criterion; a criterion the judge skipped or garbled counts as not met."""
    match = re.search(r"\{.*\}", reply, flags=re.DOTALL)
    given = {}
    try:
        for item in json.loads(match.group(0))["criteria"] if match else []:
            given[str(item["id"])] = item
    except (json.JSONDecodeError, KeyError, TypeError):
        given = {}
    verdicts = []
    for criterion in question.rubric:
        item = given.get(criterion.id)
        if item is None:
            verdicts.append({"id": criterion.id, "met": False, "reason": "The judge gave no verdict."})
        else:
            verdicts.append({"id": criterion.id, "met": item.get("met") is True, "reason": str(item.get("reason", ""))})
    return verdicts


def scores_path(results_file: Path) -> Path:
    return results_file.with_name(results_file.name.replace("results_", "scores_", 1))


def judge_run(results_file: Path, questions: dict[str, Question], judge: Judge, model: str = JUDGE_MODEL) -> Path:
    """Judge every Exploratory answer in a nao results file; save prompts and scores next to it."""
    data = json.loads(results_file.read_text())
    scores = []
    for result in data["results"]:
        question = questions.get(result["name"])
        if question is None or question.set != "exploratory":
            continue
        answer = (result.get("details") or {}).get("response_text") or ""
        entry = {"question": question.name, "attempt": result.get("attempt"), "answer": answer}
        if not answer.strip():
            # No answer (the run errored): nothing to judge, every criterion is unmet.
            entry |= {"prompt": None, "reply": None, "criteria": [
                {"id": c.id, "met": False, "reason": f"No answer: {result.get('error') or 'empty'}"}
                for c in question.rubric]}
        else:
            prompt = judge_prompt(question, answer)
            reply = judge(prompt)
            entry |= {"prompt": prompt, "reply": reply, "criteria": _verdicts(question, reply)}
        entry["score"] = sum(c["met"] for c in entry["criteria"]) / len(question.rubric)
        scores.append(entry)
    if not scores:
        raise BenchmarkError(f"{results_file}: no answers to Exploratory questions to judge.")
    path = scores_path(results_file)
    path.write_text(json.dumps({"results_file": results_file.name, "judge_model": model, "scores": scores},
                               indent=2))
    return path


def report_lines(results_dir: Path, tests_dir: Path) -> list[str]:
    """The Exploratory questions section of `demo report`: the judge's scores of each Chapter's latest run.

    Per question, a score row (mean share of rubric criteria met over the runs) and one row per
    criterion (runs that met it, out of the runs).
    """
    from compass import benchmark

    known = benchmark.questions(tests_dir)
    runs = {c: p for (c, s), p in benchmark.latest_runs(results_dir).items() if s == "exploratory"}
    judged, lines = {}, []
    for chapter, results_file in sorted(runs.items()):
        path = scores_path(results_file)
        if path.exists():
            judged[chapter] = json.loads(path.read_text())
        else:
            lines.append(f"Ch{chapter}: not judged yet ({results_file.name}).")
    if not judged:
        return lines or ["Not run yet."]

    chapters = sorted(judged)
    header = ["Question / criterion", *(f"Ch{c}" for c in chapters)]
    table = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    names = sorted({s["question"] for data in judged.values() for s in data["scores"] if s["question"] in known})
    for name in names:
        of_question = {c: [s for s in judged[c]["scores"] if s["question"] == name] for c in chapters}
        cells = [f"{sum(s['score'] for s in got) / len(got):.0%}" if got else "–" for got in of_question.values()]
        table.append("| " + " | ".join([f"{name} (score)", *cells]) + " |")
        for criterion in known[name].rubric:
            cells = []
            for got in of_question.values():
                met = sum(v["met"] for s in got for v in s["criteria"] if v["id"] == criterion.id)
                cells.append(f"{met}/{len(got)}" if got else "–")
            table.append("| " + " | ".join([f"{name}: {criterion.id}", *cells]) + " |")
    models = sorted({data.get("judge_model", "?") for data in judged.values()})
    intro = [f"Judged by {', '.join(models)} against each question's rubric (`nao/tests/exploratory/`). "
             "Score: share of rubric criteria met, averaged over the runs. Not part of Accuracy.", ""]
    return [*intro, *table, *([""] + lines if lines else [])]
