# Vendored code

| File | Upstream | Why |
|---|---|---|
| `secret.py` | the maintainer's shared tooling (not public) | The secret lookup shared with other projects: shell, then `.env`, then Infisical. See ADR 0006. |

Do not edit these files here. Maintainers change them upstream, copy them over whole, then run this repo's tests.
Demo-specific behaviour (the LLM route) belongs in `src/compass/keys.py`, not here.
