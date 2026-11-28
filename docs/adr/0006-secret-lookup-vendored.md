# The secret lookup is vendored, not depended on

The lookup behind `demo secret` (the shell, then `.env`, then Infisical through the user's login session, never printing a value) is shared with the maintainer's other projects and maintained upstream in the maintainer's own tooling. This repo keeps a byte-for-byte copy in `src/compass/vendor/secret.py`, and `src/compass/keys.py` adds only the demo's **LLM route** (Anthropic or OpenRouter) on top, and pins the vault to the `infra` project's root folder so `demo secret` behaves as before whatever `INFISICAL_PROJECT` or `INFISICAL_SECRET_PATH` say for other tools.

## Considered options

- **Read it from a sibling checkout at runtime**: rejected, followers clone this public repo alone.
- **A git dependency on the upstream**: rejected, the upstream isn't public, so `uv sync` would fail for followers.
- **Keep a separate implementation here**: rejected, two lookups drift apart and each needs its own fixes.

## Consequences

- The copy is standard library only, so it adds no dependency.
- It is updated by hand, as `src/compass/vendor/README.md` says, and never edited in place. `tests/test_keys.py` checks the demo's behaviour through `keys` and `demo secret`, so a careless update shows up there.
