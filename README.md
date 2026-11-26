# analytics-agent-crash-demo

A follow-along demo built around the fictional travel insurer **Compass Assistance**. It shows an actuarial
department moving from a **Legacy dashboard** to an **Analytics agent** backed by a **Context layer**, one
**Chapter** at a time, and measures the agent's **Accuracy** at every step. All names and data are fictional.

Everything runs locally: a DuckDB warehouse rebuilt from a seed, a Streamlit dashboard, and the
[nao](https://github.com/getnao/nao) agent. The only account you need is an Anthropic API key.

## Setup

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/). Nothing else: no Python, Node or
   database install. `uv` installs the pinned Python (3.13) and every dependency on first run.
   - macOS / Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Clone the repo and, from its root, run:

   ```sh
   uv run demo setup
   ```

   This installs the dependencies, builds the warehouse at `warehouse/compass.duckdb` and checks your API key.
3. From Chapter 2 on, the agent needs an Anthropic API key (see below).

**Platforms.** Setup is tested on macOS (Apple silicon). Windows 10/11 on x86-64 should work the same way: `uv`,
DuckDB, Streamlit and nao all ship Windows builds, and nothing needs Node or WSL. It has not been tested on
Windows yet. Run the commands from PowerShell, and set the key with `$env:ANTHROPIC_API_KEY = "sk-ant-..."`.
Windows on ARM is not supported by nao.

## Anthropic API key

The Analytics agent and the benchmark call the Anthropic API with your key. Nothing else is hosted.

```sh
export ANTHROPIC_API_KEY=sk-ant-...      # macOS / Linux
$env:ANTHROPIC_API_KEY = "sk-ant-..."    # Windows PowerShell
```

Create a key at <https://console.anthropic.com/>. Chapters 0 and 1 (warehouse and dashboard) do not need it.
Never commit it.

## Commands

| Command | What it does | Needs the key |
|---|---|---|
| `uv run demo setup` | One-time setup after cloning: dependencies, warehouse, key check | no |
| `uv run demo reset` | Rebuild the warehouse from the seed. Identical every time; use it to undo any experiment | no |
| `uv run demo dashboard` | Open the Legacy dashboard in your browser | no |
| `uv run demo chapter N` | Jump to Chapter N (see below) | no |
| `uv run demo chat` | Open the Analytics agent (nao chat) | yes |
| `uv run demo benchmark` | Run the Benchmark questions (3 runs each) for the current Chapter; `--set heldout`, `--chapter N` | yes, costs money |
| `uv run demo judge` | Score the current Chapter's Exploratory questions run against its rubric, Claude as judge; `--chapter N` | yes, costs money |
| `uv run demo report` | Turn benchmark results into the Accuracy matrix and a chart, plus Exploratory scores (`benchmark-results/`) | no |
| `uv run pytest` | Run the code tests (no key, no cost) | no |

`reset`, `setup` and `dashboard` accept `--path` (or the `COMPASS_WAREHOUSE` variable) to use another warehouse file.

## Chapters

Each Chapter is one annotated git tag named `chN-<slug>`. Its annotation says what the Chapter adds and gives its
Accuracy matrix: read it with `git show <tag>`.

| Ch | Tag | Content | Context layer |
|---|---|---|---|
| 0 | `ch0-setup` | Setup | none |
| 1 | `ch1-legacy-dashboard` | The Legacy dashboard and the pain point | none |
| 2 | `ch2-raw-schema` | Agent on the raw schema | synced table metadata only |
| 3 | `ch3-rules` | Plus Rules and annotations | Rules, per-table annotations |
| 4 | `ch4-business-glossary` | Plus the Business glossary | the Business glossary as a context document |
| 5 | `ch5-expert-judgment` | Expert judgment | the actuary's development factors, hurricane loading, Rules on immaturity |
| 6 | `ch6-metric-layer` | Metric layer | the Metric layer definitions |
| 7 | `ch7-trust` | Trust and the Ripple effect | Held-out set, regression suite, a coding agent refitting the pricing GLM |

The tags are cut while the demo is recorded; until then, `demo chapter N` reports which chapters exist.

### Jumping to a Chapter

```sh
uv run demo chapter 3
```

This

1. checks out the tag `ch3-rules`, the one annotated tag matching `ch3-*` (a detached HEAD). The Context layer is versioned, so the checkout puts it in
   exactly that chapter's state: you never see context from a later chapter;
2. rebuilds the warehouse from the seed with that chapter's code;
3. prints the chapter's annotation.

If you have local changes (for example your own context file), the jump is refused so they are not mixed into the
chapter. Commit or stash them first, or use `uv run demo chapter 3 --force` to discard them. `--force` deletes
untracked files too, but keeps ignored ones such as `.venv/` and the warehouse.

Go back to the latest version with `git switch main && uv run demo reset`. Compare two chapters with
`git diff ch3-rules ch4-business-glossary` (add `--stat` for a list of changed context files).

Run the commands from the repo root. The tag policy (tags are re-cut until recording, then frozen) and the
annotation convention are in [docs/chapters.md](docs/chapters.md).

## Benchmark and the Accuracy matrix

```sh
uv run demo chapter 3            # the Chapter whose agent you want to measure
uv run demo benchmark            # Working set; add --set heldout for the Held-out set
uv run demo report               # Accuracy matrix + chart in benchmark-results/
```

- `demo benchmark` syncs the table metadata, starts a private `nao chat` server (ports 5105/8105, so an open
  `demo chat` keeps running), signs up a throwaway local user on it, runs `nao test -k 3` on one set and stops the
  server. The run is filed under `benchmark-results/ch<N>/<set>/`. The Chapter is the `chN-*` tag checked out; on
  any other commit, say which Chapter the run is for with `--chapter N` (see
  [ADR 0004](docs/adr/0004-benchmark-runs-filed-by-chapter.md)). Re-running replaces that Chapter's result in the
  report (the latest file wins; older files are kept).
- `demo report` reads the latest run of each Chapter and set, and writes `accuracy_matrix.md` and
  `accuracy_matrix.png`. A question is correct only if all 3 runs pass. The Working set and the Held-out set are
  separate tables: Held-out results never count towards Working-set Accuracy. It needs no key and costs nothing.
- `benchmark-results/` is git-ignored, so it survives `demo chapter N` and the matrix collects a column per Chapter.

### Adding a Benchmark question

One YAML file per question in `nao/tests/working/` (or `nao/tests/heldout/`):

```yaml
name: lookup_policy_count_2025        # unique across all questions
prompt: How many policies did we write in underwriting year 2025?
tags: [tier:lookup, set:working,      # tier: lookup | definition | judgment; set matches the folder
       trap:booking_vs_policy]        # optional: the actuarial traps it probes
sql: |                                # the reference answer, from the Metric layer (metric_* views)
  SELECT count(policy_id) AS policy_count FROM metric_policies WHERE underwriting_year = 2025
```

nao compares the agent's answer with the reference SQL's result: same columns, rows in any order, numbers to 2
decimals. The warehouse file the agent queries has no Metric layer before Chapter 6
([ADR 0005](docs/adr/0005-metric-layer-applied-per-connection.md)), so `demo benchmark` computes each reference answer
through the Metric layer first and hands nao the result as literal rows (staged in the git-ignored `nao/tests/_run/`).
`uv run pytest` checks every question's tags and runs its reference SQL on a fresh warehouse; it never runs
the agent. The agent can't read `nao/tests/` (`nao/.naoignore`), so the reference SQL can't leak into its answers.

### The Working set

26 questions in `nao/tests/working/`: 8 Lookup, 8 Definition, 10 Judgment. They are asked the way an actuary
would ask them, with the ambiguity left in: the Context layer is what has to resolve it, using the definitions in
the [Business glossary](docs/business/GLOSSARY.md). Each targets one or more actuarial traps, named in its
`trap:<id>` tags:

| Trap | What goes wrong | Questions |
|---|---|---|
| `booking_vs_policy` | counting Policies where Bookings are meant | 5 |
| `pure_vs_commercial` | the wrong premium basis (A/E is on Pure premium, Loss ratio on Commercial) | 10 |
| `purchase_vs_departure` | the departure year instead of the Underwriting year (purchase) | 10 |
| `written_vs_earned` | written premium where Earned premium is meant | 7 |
| `immature_year` | treating immature 2026 as final (no IBNR) | 8 |
| `expert_judgment` | leaving out the Development factors or the Hurricane loading | 8 |
| `geographic_ae` | A/E by destination region, which the Legacy dashboard can't show | 3 |

The `expert_judgment` questions use the assumptions in their reference answers, so they are expected to fail until
Chapter 5 adds them to the context. `uv run pytest` also checks that every trap is covered, that each Expert-judgment
answer changes when the assumptions are taken out, and that no answer names a different segment, region or A/E band
when the book is drawn with another seed (so "correct" never hangs on noise).

### Exploratory questions and the rubric

Open questions such as "What's driving our underperformance?" have no single correct number. They live in
`nao/tests/exploratory/`, one YAML each with `tags: [set:exploratory]`, no `sql`, and a published `rubric`: a list
of `{id, criterion}`, each a finding a good answer makes (for example "found the destination effect", "stated that
2026 is immature", "did not invent a cause"). The rubric sits under `nao/tests/`, so the agent never sees it.

```sh
uv run demo benchmark --set exploratory   # runs them 3 times with nao test, then judges the answers
uv run demo judge                         # (re-)judge the current Chapter's latest Exploratory run
```

The judge is Claude (`claude-opus-5-5`, with your API key). Per answer it gets the question, the rubric and the
answer, and says which criteria are met. Its prompts, raw replies and per-criterion verdicts are saved next to the run
as `benchmark-results/ch<N>/exploratory/scores_<stamp>.json`, for review. `demo report` shows them in a separate
"Exploratory questions" section (score = share of criteria met, averaged over the runs, plus runs meeting each
criterion); they are never part of Accuracy or the matrix chart.

## Benchmark cost

The benchmark runs only when you ask for it, per Chapter. Each Benchmark question is asked 3 times, and each
answer is then checked by the model in a short follow-up (it writes the query that returns the final answer).

**Estimate, not yet measured:** the Working set has 26 questions, so one Chapter's run is 78 agent conversations of
roughly 30k input and 2k output tokens, plus 78 shorter checks: about 100 full conversations' worth, or **roughly
US$10 to US$30** at Claude Opus list prices. The Held-out set adds a smaller, separate run. Chat in the web UI costs cents per question. `nao test`
reports the actual cost of each run in its results, and this section will be updated with measured numbers.
Set a spending limit in the Anthropic console if you want a hard cap.

## Where things live

- `src/compass/`: the generator, warehouse, Metric layer, dashboard, Analytics agent launcher and the `demo` CLI
- `nao/`: the Analytics agent's nao project (its Context layer); `nao/tests/` holds the Benchmark questions
- `docs/`: ADRs (`docs/adr/`), the Business glossary (`docs/business/GLOSSARY.md`), the chapter tag policy
- `GLOSSARY.md`: the demo's own vocabulary
