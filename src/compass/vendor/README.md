# Vendored code

| File | Copied from | Why |
|---|---|---|
| `secret.py` | `tools/secret/secret.py` in Stephane's Home Repo (private) | The secret lookup every repo's agents share: shell, then `.env`, then Infisical. See ADR 0006. |

Copy these files whole and unchanged; do not edit them here. To update one, change it in the Home Repo, run its
tests there (`python3 -m pytest tools/secret`), copy it over this file, then run this repo's tests. Demo-specific
behaviour (the LLM route) belongs in `src/compass/keys.py`, not here.
