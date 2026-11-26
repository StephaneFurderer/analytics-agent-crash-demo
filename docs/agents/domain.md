# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, or
- **`GLOSSARY-MAP.md`** at the repo root if it exists: it points at one `GLOSSARY.md` per context. Read each one relevant to the topic.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in. In multi-context repos, also check `src/<context>/docs/adr/` for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo is multi-context. `GLOSSARY-MAP.md` at the root lists both contexts:

```
/
├── GLOSSARY-MAP.md              ← lists both contexts
├── GLOSSARY.md                  ← Demo context
├── docs/
│   ├── adr/                     ← system-wide decisions
│   └── business/GLOSSARY.md     ← Travel insurance actuarial context
```

- **Demo** (`GLOSSARY.md`): the follow-along demo itself, covering chapters, the legacy dashboard, the analytics agent, the context layer and accuracy measurement.
- **Travel insurance actuarial** (`docs/business/GLOSSARY.md`): the business glossary the analytics agent reads, such as A/E, IBNR, underwriting year and earned premium.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
