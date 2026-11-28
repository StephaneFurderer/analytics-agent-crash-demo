# Secrets

Agents get secrets through `uv run demo secret`. Never through `infisical` directly, and never by reading `.env`.
The tool reports where a secret comes from and injects it into a command. It never prints a value, so secrets stay
out of transcripts and logs.

```sh
uv run demo secret check [NAME...]                  # the LLM route, plus the source of each NAME (exit 1 if any is missing)
uv run demo secret run -- CMD ARGS                  # CMD runs with COMPASS_LLM_API_KEY / COMPASS_LLM_BASE_URL set
uv run demo secret run --name NAME -- CMD ARGS      # also inject NAME (repeatable)
```

The lookup order is: the shell, then `.env` at the repo root, then Infisical (`infra` project, `prod` environment,
through the user's `infisical login` session). The first source wins. Infisical is optional: if there is no
session, it is skipped and nothing prompts.

For the LLM, an Anthropic key (`ANTHROPIC_API_KEY` / `ANTHROPIC_API_TOKEN`) reaches Claude directly and an
OpenRouter key (`OPENROUTER_API_KEY` / `OPENROUTER_API_TOKEN`) goes through OpenRouter's Anthropic-compatible endpoint. Within a source, OpenRouter
comes first. `COMPASS_LLM_PROVIDER` forces one.

Rules:
- Run nao through `demo chat`, `demo benchmark` or `demo secret run -- nao ...`. `nao/nao_config.yaml` reads the
  `COMPASS_LLM_*` variables, which only `demo` sets.
- Never echo, log or commit a secret, and never write one into `nao_config.yaml`.
- If no session is found, ask the user to run `! infisical login`. Do not start the login yourself.

The code is in `src/compass/keys.py`, on top of `src/compass/vendor/secret.py`, a copy of the maintainer's shared
secrets tool (ADR 0006). Followers need only a key in the shell or `.env`.
