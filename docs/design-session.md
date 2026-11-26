# Design session notes (in progress)

These are working notes from a grilling session, kept so the session can resume in a new conversation. Terms that have been settled are in `/GLOSSARY.md`. Nothing gets built until the design is confirmed.

## Goal

The demo shows actuarial leaders, and hands-on actuaries following along, how to put an analytics agent (nao, https://docs.getnao.io/) to work in a travel insurance actuarial department. It is built for an actuarial summit, as about 40 minutes of recorded chapters. The narrative runs from a legacy dashboard, to an agent at about 45% accuracy, to 100% accuracy through context. A follow-on point is that the same context layer has a ripple effect: future agents (predictive models, apps) don't start from scratch.

## Settled

- **Q0:** Drop Supabase (the hosted project was paused for inactivity). Use a local DuckDB file, rebuilt by a reset command.
- **Q1:** The talk is for actuarial leaders. The repo is for hands-on actuaries to follow along.
- **Q2:** The arc is setup → without the agent (legacy dashboard) → agent on raw schema (plausible but wrong) → agent plus rules → agent plus business glossary → metric layer. Accuracy goes from about 45% to 100%.
- **Q4:** Chapters are annotated git tags on a linear history, with a script to jump between them. The user trusts the recommendation.
- **Q6:** Anthropic only, model `claude-opus-5-5`. No Ollama fallback.
- **Q7:** Recorded, not live. One recording per chapter, about 40 minutes in total, so about 8 chapters.
- **Q8:** Two glossaries: `/GLOSSARY.md` for the demo application, and a separate business glossary for the agent.
- **Q10:** The legacy dashboard is part of the demo. It is the concrete "before" (static BI or legacy tooling) and shows the pain point. Walking the agent around the dashboard is also how the business glossary gets built. The context layer is a lasting asset with a ripple effect, not a fancy new dashboard.
- **Q11:** One metric layer, read by both the dashboard and the agent.
- **Q12:** "Stronger foundation" means a stable app with few moving parts and a step-by-step build that people can follow.

- **Q2a/b:** Arc confirmed (the dictation was misheard). The term is **Metric layer**.
- **Q13:** Earning and development are critical. Immature underwriting years need actuarial expert judgment, and the agent must not assume it knows how they develop.
- **Q14:** The Ch2 traps are accepted.
- **Q17:** Actual = observed. Expected = from assumptions (pricing or forecast).
- **Q21:** Rewrite the generator, with a clean test structure.
- **Q22:** Valuation date in September 2026.
- **Q23:** Only the pricing GLM is in the warehouse. The true model is hidden ground truth.
- **Q24:** Underwriting year is a defined term, not a column.
- **Q7a:** Presentation material lives in another repo, built with the user's `/teach` skill. This repo is the follow-along application.
- **Q9:** One drift for now: a rating factor that the pricing model is missing (destination). A second drift can be added later if more material is needed.
- **Q13b:** Blending actuarial judgment into the development factors gets its own chapter. The actuary knows of development that isn't in the data, adds it, and the demo checks that the agent applies those factors correctly.
- **Q13c:** Premium is earned uniformly from purchase to return, as a simplification.
- **Q17b:** Expected defaults to the pricing basis. The forecast basis is used only when stated.
- **Q18:** Streamlit, accepted.
- **Q19:** Three tabs: Pricing, Portfolio, Performance.
- **Round 6 (all accepted):** the 8-chapter map with a separate Expert judgment chapter (Ch5); tiers T1 Lookup, T2 Definition, T3 Judgment; a cumulative accuracy matrix (ablation is a stretch goal); exploratory questions scored by a rubric with Claude as judge; a held-out set reported in Ch7; claims develop by reporting lag only (IBNR = ultimate − reported); 3 pytest layers plus `nao test`; Python CLI via uv. The insurer is **Compass Assistance**.
- **Round 7 (all accepted):**
  - Q20b: the metric catalogue (see the summary in the conversation).
  - Q25: the destination drift appears in underwriting year 2026 only, and is partly masked by immaturity at the 2026-09-30 valuation.
  - Q26: Ch5's expert judgment is a Gulf Coast hurricane in mid-September 2026, mostly unreported at valuation.
  - Q27: Ch7's ripple effect is a coding agent refitting the pricing GLM with a destination factor.
  - Q28: three ADRs (DuckDB, hidden ground truth, Streamlit), to be written once the summary is confirmed.
- **Round 8 (ticket breakdown):**
  - The Legacy dashboard uses the standard development factors from the start. Chapter 5 adds the actuary's review and the hurricane loading.
  - Claims have no development: a claim is paid in full when reported, so case reserves are always zero. The only reserves are IBNR. The full standard vocabulary is kept: Incurred = Paid + Case reserve (= Paid in this demo), and Ultimate = Incurred + IBNR. This keeps the demo focused on a small set of metrics.
  - Actual for A/E is Ultimate.
  - Ticket 12 (Held-out set) is written by the user (`ready-for-human`).
- **Deferred to build time:** Q15 (which precomputed tables to keep, to be revisited while building).

## Open (to resume)

- None. The design is confirmed and the ADRs are written in `docs/adr/` (0001–0003). Next step: build, starting from Ch0.

## Facts gathered

**nao**
- Python CLI (`pip install nao-core`, Python 3.10–3.13). Commands: `nao init`, `sync`, `chat` (localhost:5005), `test`.
- DuckDB is supported (`type: duckdb`, `path:`). SQLite is not.
- Context comes from:
  - `RULES.md`, loaded with every message
  - per-table `annotations.md`, written by hand and never overwritten
  - free-form docs folders (there is no dedicated glossary feature)
  - an optional MetricFlow semantic layer
- `nao test` runs YAML tests in `tests/` (prompt plus reference SQL) and reports pass@k. This is how accuracy will be measured.

**Prior repos**

`StephaneFurderer/travelers-nao-agent`: a nao context project only.
- Contains: Supabase Postgres config, `RULES.md` (metric formulas and guardrails), `GUIDE.md` (an executive guide with a 3-act demo), and 5 tests.

`StephaneFurderer/travel-insurance-dashboard`: Next.js 16, Supabase, Recharts and Leaflet, with 6 tabs. Metrics are computed in JavaScript and have drifted:
- pure and commercial premium are mixed
- "A/E" is year-on-year experience, not the GLM
- the GLM coefficients were copied by hand and are wrong (severity intercept 5.5 instead of 3.0)

`StephaneFurderer/travelers-demo-data`: a Python/numpy generator (seed 42) that writes to Supabase.

The data domain:
- Segments: `winter_birds`, `holiday_travelers`, `baseline`.
- Products: Hotel and Flight. A `hotel_and_flight` booking creates 2 policies.
- 38 destinations in three regions: `us_atlantic`, `gulf_coast`, `caribbean`.
- Pricing: GLM pure premium × 1.11 = commercial premium.
- The 2026 cohort is priced with the 2025 GLM, but its claims come from a shifted "2026_actual" GLM:
  - baseline segment 0.90 → 1.20
  - month 9 0.35 → 0.65
  - Caribbean +0.25
  - severity slightly higher

Generator flaws:
- claim amount equals the expected loss exactly
- frequency is a capped Bernoulli
- no claim types (`post_departure` is unused)
- purchase dates are clamped to Jan 1
- claim dates are uniform from purchase to return
- no valuation date or reporting lag
- IDs are not deterministic
- the true 2026 GLM is stored in the warehouse

**The benchouse "50% → 96%" article** (27 Oct 2026, sponsored by nao):
- It claims 96.5%, never 100%.
- The 49.6% start was Sonnet 5 on a bare schema. Opus 5.5 on a bare schema already scored 88.2%. Most of the headline gain came from switching models; the context work added about 8 points.
- The benchmark is 90 questions written by the same team that wrote the context, with an unspecified judge, 3 runs each, and no confidence intervals.

**Evidence.dev** (Nov 2026):
- Evidence Core is MIT-licensed and still exists, but the docs now use a curl-installed `evidence` CLI and push toward the hosted Evidence Studio.
- The current docs don't confirm a local DuckDB connector.
