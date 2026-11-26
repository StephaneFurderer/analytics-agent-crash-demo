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
| `uv run demo chat` | *Planned (ticket #10).* Open the Analytics agent chat | yes |
| `uv run demo benchmark` | *Planned (ticket #11).* Run the Benchmark questions for the current Chapter | yes, costs money |
| `uv run demo report` | *Planned (ticket #12).* Turn benchmark results into the Accuracy matrix and a chart | no |
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

## Benchmark cost

The benchmark runs only when you ask for it, per Chapter. Each Benchmark question is asked 3 times, and each
answer is checked by the model once more, so a run makes roughly 4 model conversations per question.

**Estimate, not yet measured:** with about 30 Working-set questions and an agent conversation of roughly 30k input
and 2k output tokens, one Chapter's run is about 100 conversations, or **roughly US$10 to US$30** at Claude Opus
list prices. The Held-out set adds a smaller, separate run. Chat in the web UI costs cents per question. `nao test`
reports the actual cost of each run in its results, and this section will be updated with measured numbers.
Set a spending limit in the Anthropic console if you want a hard cap.

## Where things live

- `src/compass/`: the generator, warehouse, Metric layer, dashboard and the `demo` CLI
- `docs/`: ADRs (`docs/adr/`), the Business glossary (`docs/business/GLOSSARY.md`), the chapter tag policy
- `GLOSSARY.md`: the demo's own vocabulary
