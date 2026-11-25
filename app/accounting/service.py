import json
from datetime import datetime, timezone

from app.accounting.periods import current_period, next_period, validate_period
from app.errors import DomainIssue
from app.evidence.manifest import stable_digest


def _load_run(runs, run_id):
    row = runs.get(run_id)
    if row is None:
        raise DomainIssue("RUN_NOT_FOUND", 404)
    return row, json.loads(row["payload"])


def _find_ticket(payload, ticket_id):
    """从已签发批次的冻结载荷里定位航段，读取封账时点的改期费。"""
    for row in payload.get("rows", []):
        if str(row.get("ticket_id", "")) == str(ticket_id):
            return row
    return None


def _ensure_open_period(store, period):
    record = store.ensure_period(period)
    if record["status"] != "open":
        raise DomainIssue("PERIOD_CLOSED", 409)
    return record


def _current_open_period(store, as_of=None):
    """当前未封账月：优先取最近的 open 账期；不存在时按自然月开账。"""
    open_record = store.current_open_period()
    if open_record is not None:
        return open_record["period"]
    return _ensure_open_period(store, current_period(as_of))["period"]


def register_correction(store, runs, request_key, run_id, ticket_id, new_fee_cents,
                        as_of=None):
    """登记航司对已签发批次改期费的更正。

    旧账（run 的载荷与证据）保持封账时点金额不动；更正差额作为
    ADJUSTMENT 分录进入当前未封账月。request_key 保证更正重试不重复入账。
    """
    existing = store.find_correction_by_request(request_key)
    if existing is not None:
        return serialize_correction(store, existing), False
    row, payload = _load_run(runs, run_id)
    if row["status"] != "APPROVED":
        raise DomainIssue("NOT_APPROVED", 409)
    ticket = _find_ticket(payload, ticket_id)
    if ticket is None:
        raise DomainIssue("TICKET_NOT_FOUND", 404)
    try:
        new_fee = int(new_fee_cents)
    except (TypeError, ValueError):
        raise DomainIssue("BAD_FEE")
    if new_fee < 0:
        raise DomainIssue("BAD_FEE")
    old_fee = int(ticket["change_fee_cents"])
    difference = new_fee - old_fee
    if difference == 0:
        raise DomainIssue("NO_DIFFERENCE")
    period = _current_open_period(store, as_of)
    record, created = store.register_correction(
        request_key, run_id, str(ticket_id), old_fee, new_fee, difference, period, difference)
    return serialize_correction(store, record), created


def reverse_correction(store, correction_id, as_of=None):
    """撤销更正。

    原 ADJUSTMENT 分录永不回改：
    - 原分录所在账期仍未封账：反向分录进同一账期，在该月内抵消；
    - 原分录所在账期已封账：反向分录进当前未封账月，撤销影响进当期。
    撤销本身幂等，重试不会再写分录。
    """
    correction = store.get_correction(correction_id)
    if correction is None:
        raise DomainIssue("CORRECTION_NOT_FOUND", 404)
    adjustment = store.get_entry(correction_id, "ADJUSTMENT")
    reversal = store.get_entry(correction_id, "REVERSAL")
    if reversal is not None or correction["status"] == "REVERSED":
        return serialize_correction(store, correction), False
    original_period = adjustment["period"]
    period_record = store.get_period(original_period)
    if period_record and period_record["status"] == "closed":
        target_period = _current_open_period(store, as_of)
        placement = "CURRENT_PERIOD"
    else:
        target_period = original_period
        placement = "SAME_PERIOD"
    amount = -int(adjustment["amount_cents"])
    if not store.add_reversal_entry(correction_id, target_period, amount):
        raise DomainIssue("CORRECTION_ALREADY_REVERSED", 409)
    store.mark_correction_reversed(correction_id)
    result = serialize_correction(store, store.get_correction(correction_id))
    result["reversal"] = {"period": target_period, "amount_cents": amount, "placement": placement}
    return result, True


def close_period(store, period):
    """封账：只冻结账期并写快照，不产生任何分录。

    因此封账失败后重试，差额仍只留在原账期，不可能进入第二个月。
    重试是幂等的：已封账直接返回同一快照；若状态已 closed 但快照缺失
    （上次在写快照前失败），按同一批分录重新补快照，金额不变。
    """
    period = validate_period(period)
    record = store.get_period(period)
    if record is None:
        raise DomainIssue("PERIOD_NOT_FOUND", 404)
    snapshot = store.get_close(period)
    if record["status"] == "closed" and snapshot is not None:
        return _close_payload(store, period, snapshot, idempotent=True)
    summary = store.period_totals(period)
    digest = stable_digest(_snapshot_body(summary))
    closed_at = datetime.now(timezone.utc).isoformat()
    snapshot = store.insert_close(summary, digest, closed_at)
    if record["status"] != "closed":
        store.mark_period_closed(period, snapshot["closed_at"])
    # 封账后自动确保存在下一个未封账月，承接后续更正
    following = next_period(period)
    store.ensure_period(following)
    return _close_payload(store, period, snapshot, idempotent=False)


def _snapshot_body(summary):
    return {"schema": "period-close/v1", **{key: summary[key] for key in
            ("period", "entry_count", "debit_total", "credit_total", "net_total")}}


def _close_payload(store, period, snapshot, idempotent):
    return {"period": period, "status": "closed", "idempotent": idempotent,
            "snapshot": {key: snapshot[key] for key in
                         ("entry_count", "debit_total", "credit_total", "net_total",
                          "snapshot_digest", "closed_at")},
            "next_open_period": next_period(period)}


def period_ledger(store, period):
    """指定账期的结算账。已封账账期以冻结快照为准。"""
    period = validate_period(period)
    record = store.get_period(period)
    if record is None:
        raise DomainIssue("PERIOD_NOT_FOUND", 404)
    entries = store.list_entries(period)
    totals = store.period_totals(period)
    close = store.get_close(period)
    body = {
        "period": period,
        "status": record["status"],
        "frozen": record["status"] == "closed",
        "entries": [serialize_entry(item) for item in entries],
        "totals": {key: totals[key] for key in
                   ("entry_count", "debit_total", "credit_total", "net_total")},
    }
    if close is not None:
        body["close"] = {key: close[key] for key in
                         ("entry_count", "debit_total", "credit_total", "net_total",
                          "snapshot_digest", "closed_at")}
        if close["snapshot_digest"] != stable_digest(_snapshot_body(totals)):
            body["snapshot_verified"] = False
        else:
            body["snapshot_verified"] = True
    return body


def list_periods(store):
    return [{"period": item["period"], "status": item["status"],
             "created_at": item["created_at"], "closed_at": item["closed_at"]}
            for item in store.open_periods()] or []


def serialize_entry(row):
    return {"entry_id": row["id"], "correction_id": row["correction_id"],
            "entry_type": row["entry_type"], "period": row["period"],
            "run_id": row["run_id"], "ticket_id": row["ticket_id"],
            "amount_cents": row["amount_cents"], "created_at": row["created_at"]}


def serialize_correction(store, row):
    adjustment = store.get_entry(row["correction_id"], "ADJUSTMENT")
    reversal = store.get_entry(row["correction_id"], "REVERSAL")
    return {
        "correction_id": row["correction_id"], "run_id": row["run_id"],
        "ticket_id": row["ticket_id"], "status": row["status"],
        "old_fee_cents": row["old_fee_cents"], "new_fee_cents": row["new_fee_cents"],
        "difference_cents": row["difference_cents"], "created_at": row["created_at"],
        "adjustment": serialize_entry(adjustment) if adjustment else None,
        "reversal": serialize_entry(reversal) if reversal else None,
    }
