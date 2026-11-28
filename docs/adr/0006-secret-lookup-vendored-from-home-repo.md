# The secret lookup is vendored from the Home Repo, not depended on

The lookup behind `demo secret` (the shell, then `.env`, then Infisical through the user's login session, never printing a value) is shared with every other repo's agents and lives in Stephane's Home Repo as `tools/secret/secret.py`. This repo keeps a byte-for-byte copy in `src/compass/vendor/secret.py`, and `src/compass/keys.py` adds only the demo's **LLM route** (Anthropic or OpenRouter) on top, and pins the vault to the `infra` project's root folder so `demo secret` behaves as before whatever `INFISICAL_PROJECT` or `INFISICAL_SECRET_PATH` say for other tools.

## Considered options

- **Read it from `../home` at runtime**: rejected, followers clone this public repo alone and have no Home Repo beside it.
- **A git dependency on the Home Repo**: rejected, the Home Repo is private, so `uv sync` would fail for followers.
- **Keep a separate implementation here**: rejected, two lookups drift apart and each needs its own fixes.

## Consequences

- The copy is standard library only, so it adds no dependency.
- It is updated by hand, as `src/compass/vendor/README.md` says, and never edited in place. `tests/test_keys.py` checks the demo's behaviour through `keys` and `demo secret`, so a careless update shows up there.
