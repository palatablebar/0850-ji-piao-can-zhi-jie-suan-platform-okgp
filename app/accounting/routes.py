from flask import Blueprint, jsonify, request, send_file
import io

from app.accounting import service
from app.accounting.render import render_ledger_csv
from app.errors import DomainIssue

accounting = Blueprint("accounting", __name__)


def stores():
    from flask import current_app
    return current_app.extensions["runs"], current_app.extensions["accounting"]


def _request_key(payload, *parts):
    base = "|".join(str(part) for part in parts)
    return "acct:" + __import__("hashlib").sha256(base.encode("utf-8")).hexdigest()[:24]


@accounting.get("/api/accounting/periods")
def periods():
    _, store = stores()
    return jsonify(periods=service.list_periods(store),
                   current_open=store.current_open_period())


@accounting.post("/api/accounting/corrections")
def create_correction():
    runs, store = stores()
    data = request.get_json(silent=True) or {}
    required = ("run_id", "ticket_id", "new_fee_cents", "request_id")
    if any(field not in data or data[field] in (None, "") for field in required):
        raise DomainIssue("BAD_REQUEST")
    key = _request_key(data, data["run_id"], data["ticket_id"],
                       data["new_fee_cents"], data["request_id"])
    result, created = service.register_correction(
        store, runs, key, str(data["run_id"]), str(data["ticket_id"]),
        data["new_fee_cents"])
    result["created"] = created
    return jsonify(result), 201 if created else 200


@accounting.get("/api/accounting/corrections/<correction_id>")
def get_correction(correction_id):
    _, store = stores()
    correction = store.get_correction(correction_id)
    if correction is None:
        raise DomainIssue("CORRECTION_NOT_FOUND", 404)
    return jsonify(service.serialize_correction(store, correction))


@accounting.post("/api/accounting/corrections/<correction_id>/reverse")
def reverse(correction_id):
    _, store = stores()
    result, created = service.reverse_correction(store, correction_id)
    result["reversed_now"] = created
    return jsonify(result)


@accounting.post("/api/accounting/periods/<period>/close")
def close(period):
    _, store = stores()
    return jsonify(service.close_period(store, period))


@accounting.get("/api/accounting/periods/<period>/ledger")
def ledger(period):
    _, store = stores()
    body = service.period_ledger(store, period)
    fmt = (request.args.get("format") or "json").lower()
    if fmt == "csv":
        raw = render_ledger_csv(body)
        return send_file(
            io.BytesIO(raw), mimetype="text/csv; charset=utf-8",
            as_attachment=True, download_name=f"settlement_{period}.csv")
    if fmt != "json":
        raise DomainIssue("BAD_REQUEST")
    return jsonify(body)
