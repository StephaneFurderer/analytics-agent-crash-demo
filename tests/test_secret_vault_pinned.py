"""`demo secret` reads the `infra` project's root folder, whatever other tools set INFISICAL_PROJECT or
INFISICAL_SECRET_PATH to (ADR 0006)."""

from compass import keys


def requests_for(monkeypatch):
    seen = []

    def get_json(url, token):
        seen.append(url)
        if url.endswith("/v1/workspace"):
            return {"workspaces": [{"id": "p-infra", "name": "infra", "slug": "infra"},
                                   {"id": "p-web", "name": "web", "slug": "web"}]}
        return {"secret": {"secretValue": "synthetic"}}

    monkeypatch.setattr(keys.Infisical, "from_session",
                        classmethod(lambda cls: cls("jwt", api_url="https://vault.example/api", get_json=get_json)))
    return seen


def test_another_tools_project_and_folder_do_not_move_the_demos_vault(monkeypatch):
    monkeypatch.setenv("INFISICAL_PROJECT", "web")
    monkeypatch.setenv("INFISICAL_SECRET_PATH", "/newsfeed")
    seen = requests_for(monkeypatch)

    assert keys.lookup("DEPLOY_TOKEN").source == "Infisical"
    assert "projectId=p-infra" in seen[-1] and "secretPath=%2F&" in seen[-1] + "&"
