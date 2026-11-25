from datetime import date

import pytest

from app.accounting.periods import current_period, next_period
from app.accounting.service import (close_period, period_ledger,
                                    register_correction, reverse_correction)
from app.accounting.store import AccountingStore
from app.errors import DomainIssue
from app.review.store import Store


@pytest.fixture
def stores(tmp_path):
    db = tmp_path / "acct.sqlite3"
    runs = Store(str(db))
    acct = AccountingStore(str(db))
    return runs, acct


def approved_run(runs, profile="clean"):
    from app.service import pipeline
    from app.review.service import approve, create_run
    run = create_run(runs, pipeline(profile))
    if run["status"] != "APPROVED":
        run = approve(runs, run["run_id"], "APPROVED", "封账前签发", run["revision"])
    return runs.get(run["run_id"])


def correct(store, runs, as_of, request_id="R1", run_id=None, ticket="T3", new_fee=1200):
    run_id = run_id or approved_run(runs)["id"]
    key = f"acct:test:{request_id}"
    return register_correction(store, runs, key, run_id, ticket, new_fee, as_of=as_of)


# ---- 更正差额进入当前未封账月，旧账保持原金额 -----------------------------

def test_correction_posts_difference_into_current_open_period(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    period = current_period(as_of)
    result, created = correct(store, runs, as_of)
    assert created is True
    assert result["old_fee_cents"] == 800          # clean.csv 中 T3 改期费 800 分
    assert result["new_fee_cents"] == 1200
    assert result["difference_cents"] == 400
    assert result["adjustment"]["period"] == period
    assert result["adjustment"]["amount_cents"] == 400
    ledger = period_ledger(store, period)
    assert ledger["status"] == "open"
    assert ledger["totals"]["net_total"] == 400


def test_original_run_payload_keeps_booked_amount(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    run_row = approved_run(runs)
    correct(store, runs, as_of, run_id=run_row["id"])
    import json
    payload = json.loads(runs.get(run_row["id"])["payload"])
    ticket = next(row for row in payload["rows"] if row["ticket_id"] == "T3")
    assert ticket["change_fee_cents"] == 800       # 封账时点金额不被更正改写


def test_correction_requires_approved_run(stores):
    runs, store = stores
    from app.service import pipeline
    from app.review.service import create_run
    run = create_run(runs, pipeline("clean"))     # DRAFT，未签发
    with pytest.raises(DomainIssue) as exc:
        register_correction(store, runs, "k", run["run_id"], "T3", 1200,
                            as_of=date(2026, 10, 15))
    assert exc.value.code == "NOT_APPROVED"


def test_unknown_ticket_and_zero_difference_are_rejected(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    run_id = approved_run(runs)["id"]
    with pytest.raises(DomainIssue) as exc:
        correct(store, runs, as_of, run_id=run_id, ticket="NOPE", new_fee=900)
    assert exc.value.code == "TICKET_NOT_FOUND"
    with pytest.raises(DomainIssue) as exc2:
        correct(store, runs, as_of, request_id="R2", run_id=run_id,
                ticket="T3", new_fee=800)
    assert exc2.value.code == "NO_DIFFERENCE"


# ---- 更正重试不重复入账 ----------------------------------------------------

def test_correction_retry_is_idempotent(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    first, created1 = correct(store, runs, as_of, request_id="DUP")
    second, created2 = correct(store, runs, as_of, request_id="DUP")
    assert created1 is True and created2 is False
    assert first["correction_id"] == second["correction_id"]
    ledger = period_ledger(store, current_period(as_of))
    assert ledger["totals"]["entry_count"] == 1
    assert ledger["totals"]["net_total"] == 400


# ---- 封账：冻结旧账、快照可对账、失败重试不串月 -----------------------------

def test_closed_period_keeps_booked_amount_and_snapshot(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    period = current_period(as_of)
    correct(store, runs, as_of)
    result = close_period(store, period)
    assert result["status"] == "closed"
    assert result["snapshot"]["entry_count"] == 1
    assert result["snapshot"]["net_total"] == 400
    assert len(result["snapshot"]["snapshot_digest"]) == 64
    # 旧账仍按封账时金额对账
    ledger = period_ledger(store, period)
    assert ledger["frozen"] is True
    assert ledger["snapshot_verified"] is True
    assert ledger["totals"]["net_total"] == 400


def test_new_correction_after_close_goes_to_next_open_month(stores):
    runs, store = stores
    october = current_period(date(2026, 10, 15))
    correct(store, runs, date(2026, 10, 15), request_id="OCT")
    close_period(store, october)
    # 11 月再次更正同票：差额进当前未封账月，10 月旧账不动
    result, _ = correct(store, runs, date(2026, 11, 3), request_id="NOV", new_fee=1500)
    assert result["difference_cents"] == 700
    assert result["adjustment"]["period"] == "2026-11"
    oct_ledger = period_ledger(store, october)
    assert oct_ledger["totals"]["net_total"] == 400
    nov_ledger = period_ledger(store, "2026-11")
    assert nov_ledger["totals"]["net_total"] == 700


def test_close_retry_after_failure_keeps_difference_in_one_month(stores):
    runs, store = stores
    period = current_period(date(2026, 10, 15))
    correct(store, runs, date(2026, 10, 15))
    close_period(store, period)
    # 模拟封账流程在快照落库前失败：状态已 closed 但 period_closes 缺行
    with store.connect() as db:
        db.execute("DELETE FROM period_closes WHERE period=?", (period,))
    retry = close_period(store, period)
    assert retry["snapshot"]["entry_count"] == 1
    assert retry["snapshot"]["net_total"] == 400
    # 差额没有被复制到任何其他月份
    following = next_period(period)
    assert period_ledger(store, period)["totals"]["entry_count"] == 1
    assert store.get_period(following)["status"] == "open"
    nov = period_ledger(store, following)
    assert nov["totals"]["entry_count"] == 0 and nov["totals"]["net_total"] == 0
    # 再次重试完全幂等
    again = close_period(store, period)
    assert again["idempotent"] is True
    assert again["snapshot"]["snapshot_digest"] == retry["snapshot"]["snapshot_digest"]


def test_closed_period_record_rejects_new_entries_defensively(stores):
    runs, store = stores
    period = current_period(date(2026, 10, 15))
    correct(store, runs, date(2026, 10, 15))
    close_period(store, period)
    record = store.get_period(period)
    assert record["status"] == "closed"
    # 服务层永远不会选已封账账期；直接对封账账期 ensure 也必须被拦截
    from app.accounting.service import _ensure_open_period
    with pytest.raises(DomainIssue) as exc:
        _ensure_open_period(store, period)
    assert exc.value.code == "PERIOD_CLOSED"
    # 后续更正只能落到自动开出的新账期
    following = next_period(period)
    assert store.get_period(following)["status"] == "open"


# ---- 撤销：未封账同月抵消，已封账影响进当期 -------------------------------

def test_reversal_in_open_month_offsets_in_same_period(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    period = current_period(as_of)
    correction, _ = correct(store, runs, as_of)
    result, reversed_now = reverse_correction(store, correction["correction_id"], as_of=as_of)
    assert reversed_now is True
    assert result["reversal"]["placement"] == "SAME_PERIOD"
    assert result["reversal"]["period"] == period
    ledger = period_ledger(store, period)
    assert ledger["totals"]["entry_count"] == 2
    assert ledger["totals"]["net_total"] == 0       # 同月内正负抵消


def test_reversal_after_close_lands_in_current_period(stores):
    runs, store = stores
    october = current_period(date(2026, 10, 15))
    correction, _ = correct(store, runs, date(2026, 10, 15))
    close_period(store, october)
    result, _ = reverse_correction(store, correction["correction_id"],
                                   as_of=date(2026, 11, 8))
    assert result["reversal"]["placement"] == "CURRENT_PERIOD"
    assert result["reversal"]["period"] == "2026-11"
    oct_ledger = period_ledger(store, october)
    assert oct_ledger["totals"]["net_total"] == 400   # 已封账差额留在原月
    nov_ledger = period_ledger(store, "2026-11")
    assert nov_ledger["totals"]["net_total"] == -400  # 撤销影响进当期


def test_reversal_retry_does_not_double_post(stores):
    runs, store = stores
    as_of = date(2026, 10, 15)
    correction, _ = correct(store, runs, as_of)
    reverse_correction(store, correction["correction_id"], as_of=as_of)
    again, reversed_now = reverse_correction(store, correction["correction_id"], as_of=as_of)
    assert reversed_now is False
    ledger = period_ledger(store, current_period(as_of))
    assert ledger["totals"]["entry_count"] == 2
    assert ledger["totals"]["net_total"] == 0


# ---- 结算账下载数据 --------------------------------------------------------

def test_ledger_is_available_for_any_known_period(stores):
    runs, store = stores
    period = current_period(date(2026, 10, 15))
    correct(store, runs, date(2026, 10, 15))
    ledger = period_ledger(store, period)
    assert ledger["period"] == period
    assert {entry["entry_type"] for entry in ledger["entries"]} == {"ADJUSTMENT"}
    with pytest.raises(DomainIssue) as exc:
        period_ledger(store, "2020-01")
    assert exc.value.code == "PERIOD_NOT_FOUND"
    with pytest.raises(DomainIssue):
        period_ledger(store, "2020-13")
