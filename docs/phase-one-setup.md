# Phase one: setup and architecture decisions

Phase one is everything you do before the Analytics agent answers its first question (Chapters 0 to 2). First you
work through the setup checklist, then the decision questions. Each question gives the options and the demo's
default. You can keep the default, but write down why. The benchmark from Chapter 2 on is how you find out whether
your choices were good.

## 1. Setup checklist

| # | Step | Command / where | Done when |
|---|---|---|---|
| 1 | Install `uv` (nothing else: no Python, Node or database) | see the README | `uv --version` works |
| 2 | Clone the repo and set up | `uv run demo setup` | it prints the warehouse path |
| 3 | Check the code works | `uv run pytest` | all tests pass, with no key and no cost |
| 4 | Look at the data | `uv run demo dashboard` | the Pricing, Portfolio and Performance tabs open |
| 5 | Choose an LLM provider and get a key | questions A1 to A3 below | you have one key |
| 6 | Store the key | shell, `.env` (copy `.env.example`) or Infisical | `uv run demo secret check` shows a route |
| 7 | Set a spending cap | Anthropic or OpenRouter console | a monthly limit is set |
| 8 | Open the agent and ask one simple question | `uv run demo chat`, e.g. "How many policies were sold in 2025?" | it answers from the warehouse |
| 9 | Record the baseline (it costs money) | `uv run demo benchmark --chapter 2`, then `uv run demo report` | `benchmark-results/accuracy_matrix.md` has a Ch2 row |

## 2. Decision questions

### A. The LLM

**A1. Which model does the agent run on?**
The options are a frontier model (Claude Opus), a mid-tier model (Claude Sonnet), or a small, cheap one.
Default: Claude Opus 5.5.
To decide, ask how much a wrong actuarial number costs compared with the cost of a benchmark run. Bigger models
usually make fewer SQL and reasoning mistakes, but a good Context layer (Chapters 3 to 6) can close much of that gap.
That is the point of the demo.

**A2. Do you call the provider directly or through a router?**
The options are direct to Anthropic (`ANTHROPIC_API_KEY`), or through OpenRouter (`OPENROUTER_API_KEY`), which is
one key for many vendors.
Default: whichever key you have. `demo` supports both.
To decide, weigh price (OpenRouter adds a fee), data handling (one more company sees your prompts and data), ease of
swapping models for comparison, and what your organisation already pays for.

**A3. Should the judge be the same model as the agent?**
The Exploratory questions are scored by an LLM judge.
Default: the same model on the same route.
To decide, consider that a model judging its own answers may be lenient. A different model, or a human spot-check on
a sample, makes the scores more trustworthy but costs more.

**A4. Where may the data go?**
Every question sends schema metadata, sample rows (`preview.md`) and query results to the LLM provider.
Default: acceptable, because all the data is fictional.
To decide, ask whether a real portfolio could leave your network. If not, you need a provider with a data-processing
agreement, a cloud region you control (AWS Bedrock or Google Vertex), or a local model (Ollama). nao supports all
of these, but the demo is wired for Anthropic and OpenRouter only: anything else is a change you make in your fork.

### B. The architecture

**B1. Which agent framework?**
The options are nao (open source, local, with a built-in benchmark runner), a vendor's hosted analytics agent, or a
framework you build yourself on an LLM SDK.
Default: nao.
To decide, look at how context is managed (files you can version in git versus a hosted UI), whether there is a
built-in evaluation, lock-in, and who will maintain it.

**B2. Where does the warehouse live?**
The options are local DuckDB, cloud DuckDB (MotherDuck), or your company's warehouse (Snowflake, BigQuery,
Postgres, and so on).
Default: local DuckDB, rebuilt from a seed, so every follower has identical data.
To decide, think about reproducibility, cost, and how close the setup is to the warehouse you will really use.

**B3. Where do business definitions live: in the warehouse or in the agent's context?**
The options are a Metric layer in SQL (views), annotations and a glossary in the Context layer, or both.
Default: both, introduced one at a time in Chapters 3 to 6 so you can see what each adds.
To decide, consider that a single source of truth helps the dashboard and the agent agree, while context the agent
reads is quicker to change. See ADR 0005.

**B4. How do you measure "good enough"?**
The options are exact-match Benchmark questions, rubric-judged Exploratory questions, a human review, or a mix.
Default: a Working set and a Held-out set (exact match, each question asked 3 times, correct only if all 3 runs are
right), plus Exploratory questions with a rubric.
To decide, ask what Accuracy you need before an actuary may rely on an answer unchecked, and who writes the
Held-out questions so they stay unseen.

### C. Operations

**C1. Where do secrets live?**
The options are the shell, a `.env` file, or a secrets manager (Infisical, Vault, a cloud secrets service).
Default: whichever you prefer. `demo secret check` shows which one is in use.
To decide, compare a solo laptop, a shared team key that needs rotating, CI, and audit needs. A `.env` file is
simplest. A secrets manager means nobody copies keys around.

**C2. What budget do you set, and who watches it?**
The options are a provider spending cap, per-run cost tracking (`nao test` reports the cost), or both.
Default: a cap in the console, plus reading each run's cost in its results.
To decide, note that one benchmark run is estimated at US$10 to US$30 (see the README). Multiply that by the number
of Chapters and reruns.

**C3. Who can see and change the agent's context?**
The options are anyone via git pull requests, a named owner per table or metric, or the actuarial team only.
Default: git, with review.
To decide, remember that from Chapter 5 on the context holds expert judgment, such as development assumptions. A
change there changes the agent's answers, just as editing an assumption file changes a reserve.

## 3. Record your choices

Copy this into your notes or your fork's README. Bring it to Chapter 2 and compare it with your baseline Accuracy.

```text
A1 model:            A2 route:            A3 judge:            A4 data:
B1 framework:        B2 warehouse:        B3 definitions:      B4 measure:
C1 secrets:          C2 budget:           C3 context owner:
Baseline Accuracy (Ch2, Working set):
```
