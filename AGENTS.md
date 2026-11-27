# AGENTS.md

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues on StephaneFurderer/analytics-agent-crash-demo, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context: `GLOSSARY-MAP.md` links the Demo glossary (`GLOSSARY.md`) and the Travel insurance actuarial business glossary (`docs/business/GLOSSARY.md`); system-wide ADRs live in `docs/adr/`. See `docs/agents/domain.md`.

### Secrets

Get API keys and other secrets with `uv run demo secret check|run`, which reads the shell, then `.env`, then Infisical (`infra`/`prod`). It never prints values. See `docs/agents/secrets.md`.
