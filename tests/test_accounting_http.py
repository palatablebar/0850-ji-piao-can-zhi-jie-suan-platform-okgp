import csv
import io
from datetime import date


def approve_clean(client):
    run = client.post("/api/runs", json={"profile": "clean"}).get_json()
    client.post(f"/api/runs/{run['run_id']}/review",
                json={"decision": "APPROVED", "comment": "ok", "expected_revision": 0})
    return run


def make_correction(client, run, new_fee=1200, request_id="airline-1"):
    return client.post("/api/accounting/corrections", json={
        "run_id": run["run_id"], "ticket_id": "T3",
        "new_fee_cents": new_fee, "request_id": request_id})


def test_periods_start_empty(client):
    data = client.get("/api/accounting/periods").get_json()
    assert data == {"periods": [], "current_open": None}


def test_correction_lifecycle_over_http(client):
    run = approve_clean(client)
    response = make_correction(client, run)
    assert response.status_code == 201
    correction = response.get_json()
    assert correction["difference_cents"] == 400
    assert correction["adjustment"]["period"] == date.today().strftime("%Y-%m")
    # 重试同一请求：幂等，不重复入账
    retry = make_correction(client, run)
    assert retry.status_code == 200
    assert retry.get_json()["correction_id"] == correction["correction_id"]
    period = correction["adjustment"]["period"]
    ledger = client.get(f"/api/accounting/periods/{period}/ledger").get_json()
    assert ledger["totals"]["entry_count"] == 1
    # 撤销：未封账，同月抵消
    reversed_resp = client.post(
        f"/api/accounting/corrections/{correction['correction_id']}/reverse")
    assert reversed_resp.status_code == 200
    assert reversed_resp.get_json()["reversal"]["placement"] == "SAME_PERIOD"
    ledger = client.get(f"/api/accounting/periods/{period}/ledger").get_json()
    assert ledger["totals"]["entry_count"] == 2
    assert ledger["totals"]["net_total"] == 0


def test_close_freeze_and_reopen_next_month(client):
    run = approve_clean(client)
    correction = make_correction(client, run).get_json()
    period = correction["adjustment"]["period"]
    closed = client.post(f"/api/accounting/periods/{period}/close")
    assert closed.status_code == 200
    body = closed.get_json()
    assert body["status"] == "closed"
    assert body["snapshot"]["net_total"] == 400
    # 封账重试幂等，返回同一快照摘要
    again = client.post(f"/api/accounting/periods/{period}/close").get_json()
    assert again["idempotent"] is True
    assert again["snapshot"]["snapshot_digest"] == body["snapshot"]["snapshot_digest"]
    # 已封账账期的结算账标记冻结且快照校验通过
    ledger = client.get(f"/api/accounting/periods/{period}/ledger").get_json()
    assert ledger["frozen"] is True and ledger["snapshot_verified"] is True
    # 封账自动开下月；新更正进下月，旧月金额不变
    follow = make_correction(client, run, new_fee=1500, request_id="airline-2").get_json()
    assert follow["adjustment"]["period"] == body["next_open_period"]
    old = client.get(f"/api/accounting/periods/{period}/ledger").get_json()
    assert old["totals"]["net_total"] == 400


def test_reversal_after_close_hits_current_period(client):
    run = approve_clean(client)
    correction = make_correction(client, run).get_json()
    period = correction["adjustment"]["period"]
    client.post(f"/api/accounting/periods/{period}/close")
    response = client.post(
        f"/api/accounting/corrections/{correction['correction_id']}/reverse")
    body = response.get_json()
    assert body["reversal"]["placement"] == "CURRENT_PERIOD"
    assert body["reversal"]["period"] != period
    frozen = client.get(f"/api/accounting/periods/{period}/ledger").get_json()
    assert frozen["totals"]["net_total"] == 400      # 已封账差额留在原月


def test_ledger_download_json_and_csv(client):
    run = approve_clean(client)
    correction = make_correction(client, run).get_json()
    period = correction["adjustment"]["period"]
    raw = client.get(f"/api/accounting/periods/{period}/ledger?format=csv")
    assert raw.status_code == 200
    assert raw.mimetype == "text/csv"
    disposition = raw.headers["Content-Disposition"]
    assert f"settlement_{period}.csv" in disposition
    text = raw.data.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "账期"
    assert rows[1][2] == "ADJUSTMENT" and int(rows[1][6]) == 400
    assert any("净额(分)" in cell for cell in rows)
    # 未知账期与非法格式
    assert client.get("/api/accounting/periods/1999-09/ledger").status_code == 404
    bad = client.get(f"/api/accounting/periods/{period}/ledger?format=pdf")
    assert bad.status_code == 400


def test_bad_requests_are_rejected(client):
    run = approve_clean(client)
    missing = client.post("/api/accounting/corrections", json={"run_id": run["run_id"]})
    assert missing.status_code == 400
    bad_period = client.post("/api/accounting/periods/2026-13/close")
    assert bad_period.status_code == 400
    assert client.post("/api/accounting/periods/2030-01/close").status_code == 404
    assert client.post("/api/accounting/corrections/nope/reverse").status_code == 404


def test_correction_on_draft_run_is_blocked(client):
    run = client.post("/api/runs", json={"profile": "clean"}).get_json()
    response = make_correction(client, run)
    assert response.status_code == 409
    assert response.get_json()["code"] == "NOT_APPROVED"


def test_evidence_payload_remains_unchanged_after_correction(client):
    run = approve_clean(client)
    before = client.get(f"/api/runs/{run['run_id']}/evidence").get_json()
    make_correction(client, run)
    after = client.get(f"/api/runs/{run['run_id']}/evidence").get_json()
    assert after == before
