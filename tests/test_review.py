from tests.domain_cases import run_profile


def create(client, profile="clean"):
    response = client.post("/api/runs", json={"profile": profile})
    assert response.status_code == 200
    return response.get_json()


def test_clean_run_is_created(client):
    run = create(client)
    assert run["status"] == "DRAFT"
    assert run["revision"] == 0


def test_same_request_is_idempotent(client):
    first = create(client)
    second = create(client)
    assert first["run_id"] == second["run_id"]
    assert first["counts"] == second["counts"]


def test_clean_run_can_be_approved(client):
    run = create(client)
    response = client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "已核验", "expected_revision": 0})
    assert response.status_code == 200
    assert response.get_json()["status"] == "APPROVED"


def test_dirty_run_is_blocked(client):
    run = create(client, "dirty")
    response = client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "尝试签发", "expected_revision": 0})
    assert response.status_code == 409
    assert response.get_json()["code"] == "GATE_BLOCKED"


def test_stale_revision_is_rejected(client):
    run = create(client)
    first = client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "首次", "expected_revision": 0})
    assert first.status_code == 200
    second = client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "旧版本", "expected_revision": 0})
    assert second.status_code == 409
    assert second.get_json()["code"] == "STALE_REVIEW"


def test_comment_is_saved(client):
    run = create(client)
    response = client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "复核通过", "expected_revision": 0})
    assert response.get_json()["comment"] == "复核通过"
