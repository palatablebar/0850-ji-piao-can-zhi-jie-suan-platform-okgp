def approved(client):
    run = client.post("/api/runs", json={"profile": "clean"}).get_json()
    client.post(f"/api/runs/{run['run_id']}/review", json={"decision": "APPROVED", "comment": "复核完成", "expected_revision": 0})
    return run


def test_unapproved_evidence_is_blocked(client):
    run = client.post("/api/runs", json={"profile": "clean"}).get_json()
    response = client.get(f"/api/runs/{run['run_id']}/evidence")
    assert response.status_code == 409


def test_approved_evidence_downloads(client):
    run = approved(client)
    response = client.get(f"/api/runs/{run['run_id']}/evidence")
    assert response.status_code == 200
    assert response.get_json()["schema"] == "workbench-evidence/v1"


def test_evidence_keeps_run_id(client):
    run = approved(client)
    assert client.get(f"/api/runs/{run['run_id']}/evidence").get_json()["run_id"] == run["run_id"]


def test_evidence_keeps_source_digest(client):
    run = approved(client)
    artifact = client.get(f"/api/runs/{run['run_id']}/evidence").get_json()
    assert artifact["source"]["sha256"] == run["source"]["sha256"]


def test_evidence_records_review_revision(client):
    run = approved(client)
    artifact = client.get(f"/api/runs/{run['run_id']}/evidence").get_json()
    assert artifact["review"] == {"status": "APPROVED", "revision": 1, "comment": "复核完成"}


def test_artifact_has_stable_digest(client):
    run = approved(client)
    artifact = client.get(f"/api/runs/{run['run_id']}/evidence").get_json()
    assert len(artifact["artifact_sha256"]) == 64
