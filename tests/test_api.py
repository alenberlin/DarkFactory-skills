"""Real API identities, replay protection and browser-origin boundaries."""

from pathlib import Path

from fastapi.testclient import TestClient

from darkfactory.api import create_app
from darkfactory.domain import Policy
from darkfactory.storage import Store
from tests.test_contracts import blueprint


def test_admin_auth_origin_and_exact_approval_digest(tmp_path: Path) -> None:
    store = Store(tmp_path / "state")
    project = store.create_project(blueprint(), Policy(required_check_kinds=["test"]))
    token = "fixture-operator-credential-for-tests-only"
    client = TestClient(create_app(store, token), base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer " + token}
    path = f"/v1/projects/{project}/approve"
    assert client.get("/v1/projects").status_code == 401
    assert (
        client.post(path, headers={"X-Actor": "human:fake"}, json={"digest": "x" * 64}).status_code
        == 401
    )
    assert (
        client.post(
            path,
            headers={**headers, "Origin": "https://attacker.example"},
            json={"digest": "x" * 64},
        ).status_code
        == 403
    )
    assert client.post(path, headers=headers, json={"digest": "x" * 64}).status_code == 409
    payload = {"digest": store.project(project)["blueprint_hash"]}
    assert (
        client.post(path, headers=headers, json={**payload, "actor": "human:fake"}).status_code
        == 422
    )
    assert client.post(path, headers=headers, json=payload).status_code == 200
    assert client.post(path, headers=headers, json=payload).status_code == 409
    assert (
        client.get("/v1/projects", headers={**headers, "Host": "attacker.example"}).status_code
        == 403
    )
    assert client.get("/").status_code == 200
    invalid = client.post(
        path, headers=headers, json={"digest": "short", "password": "sensitive-fixture-only"}
    )
    assert invalid.status_code == 422
    assert "sensitive-fixture-only" not in invalid.text
