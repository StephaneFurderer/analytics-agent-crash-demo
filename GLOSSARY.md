# Analytics Agent Demo

A follow-along demo, built around the fictional insurer **Compass Assistance**, recorded chapter by chapter, that shows an actuarial department how to move from a **Legacy dashboard** to an **Analytics agent** backed by a **Context layer**. This is the glossary of the demo itself. The actuarial definitions the agent reads live in the separate **Business glossary**.

## Language

### The story

**Chapter**:
One step of the demo. It is recorded as one video segment, and followers can jump to it in the repo.
_Avoid_: Step, lesson, branch

**Compass Assistance**:
The fictional travel insurer whose book the demo analyses.
_Avoid_: Travelers, the company, the client

**Legacy dashboard**:
A fixed, pre-built dashboard that stands for how an actuarial department analyses its book today. It answers only the questions someone thought of in advance.
_Avoid_: BI dashboard, old app, the dashboard app

**Analytics agent**:
The chat agent that answers business questions in natural language by querying the warehouse.
_Avoid_: Chatbot, the AI, copilot

### Measuring the agent

**Accuracy**:
The share of **Benchmark questions** the **Analytics agent** answers correctly on every repeated run. It is the headline measure of progress across **Chapters**.
_Avoid_: Pass rate, score

**Benchmark question**:
A business question with a known correct answer, used to measure **Accuracy**. Each one belongs to a **Tier**, and to either the **Working set** or the **Held-out set**.
_Avoid_: Test, eval, prompt

**Tier**:
The difficulty class of a **Benchmark question**: Lookup (one metric, one filter), Definition (depends on an agreed definition) or Judgment (needs **Expert judgment** or a multi-step diagnosis).
_Avoid_: Level, difficulty

**Working set**:
The **Benchmark questions** used while building the **Context layer**.
_Avoid_: Training set, dev set

**Held-out set**:
**Benchmark questions** written before any context work and never used to tune the **Context layer**.
_Avoid_: Test set, blind set

**Exploratory question**:
An open business question with no single correct number. It is scored against a published rubric, separately from **Accuracy**.
_Avoid_: Open question, free-form question

**Accuracy matrix**:
**Accuracy** by **Tier** and **Chapter**. It shows the effect of each piece of the **Context layer**.
_Avoid_: Scorecard, leaderboard

### Context

**Context layer**:
Everything an agent reads besides the raw data: **Rules**, table annotations, the **Business glossary** and the **Metric layer**. It is a lasting asset, not something set up once for a single agent.
_Avoid_: Prompt, semantic model, knowledge base

**Rules**:
Standing instructions the **Analytics agent** receives with every question.
_Avoid_: System prompt, guardrails

**Business glossary**:
The actuarial definitions the department has agreed on, written for agents and people to read. It is part of the **Context layer**.
_Avoid_: Data dictionary, dictionary

**Metric layer**:
The single governed definition of every metric. The **Legacy dashboard** and the **Analytics agent** both read it, so their numbers cannot disagree.
_Avoid_: Analytics layer, semantic layer, KPI logic

**Ripple effect**:
Other agents reusing the **Context layer** beyond chat, for example to build a predictive model or a new application without starting from scratch.
_Avoid_: Spillover, side benefit
