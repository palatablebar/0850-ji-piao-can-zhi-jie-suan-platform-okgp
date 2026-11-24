import json
from decimal import Decimal
from pathlib import Path

from app.catalog import SPEC
from app.domain.calculate import calculate_rows
from app.domain.decision import decide_rows
from app.domain.prepare import prepare_rows
from app.intake.service import load
from app.reconcile.ledger import build_ledger


def jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items() if not str(key).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def _stage(name):
    return SPEC["stages"].index(name) + 1


def pipeline(profile="dirty", path=None, upto="证据交付"):
    intake = load(profile, path)
    prepared, prepare_issues = [], []
    results = []
    ledger = None
    if _stage(upto) >= 2:
        prepared, prepare_issues = prepare_rows(intake["rows"])
    if _stage(upto) >= 3:
        results = calculate_rows(prepared)
    if _stage(upto) >= 4:
        results = decide_rows(results)
    if _stage(upto) >= 5:
        ledger = build_ledger(intake, prepared, prepare_issues, results)
    intake["counts"]["prepared"] = len(prepared)
    intake["counts"]["computed"] = len(results)
    issues = intake["issues"] + prepare_issues
    summary = {"PASS": 0, "REVIEW": 0, "REJECT": 0}
    for item in results:
        summary[item.get("verdict", "REVIEW")] = summary.get(item.get("verdict", "REVIEW"), 0) + 1
    chart_field = {"0840": "rolling", "0849": "mean", "0850": "settlement_cents"}.get(SPEC["code"], "metric")
    chart = [{"label": item.get("label", item.get(SPEC["key"], "")),
              "value": float(item.get(chart_field) or 0),
              "limit": float(item.get("limit") or 0)}
             for item in results[:12]]
    rows = []
    raw_stage = _stage(upto) <= 2
    if raw_stage:
        stage_rows = intake["rows"] if _stage(upto) == 1 else prepared
        rows = [{key: item.get(key) for key in SPEC["columns"]} for item in stage_rows[:18]]
    else:
        for item in results[:18]:
            rows.append({key: value for key, value in item.items()
                         if key in {"label", "verdict", "reason", "metric", "limit", "status", "state", "breakdown"}
                         or key in SPEC["columns"] or key in SPEC["result_columns"]})
    source = {"profile": profile, "filename": Path(intake["path"]).name, "sha256": intake["sha256"]}
    payload = {
        "project": SPEC["code"] + " " + SPEC["name"],
        "rule": SPEC["rule_short"],
        "profile": profile,
        "source": source,
        "counts": intake["counts"],
        "issues": issues[:60],
        "rows": rows,
        "row_kind": "source" if raw_stage else "result",
        "chart": chart,
        "summary": summary,
        "ledger": ledger,
        "stages": [{"id": "intake", "name": SPEC["stages"][0]},
                   {"id": "prepare", "name": SPEC["stages"][1]},
                   {"id": "calculate", "name": SPEC["stages"][2]},
                   {"id": "decision", "name": SPEC["stages"][3]},
                   {"id": "reconcile", "name": SPEC["stages"][4]}],
        "run_key": __import__("hashlib").sha256(
            (SPEC["code"] + profile + intake["sha256"] + SPEC["rule"]).encode("utf-8")).hexdigest()[:24],
    }
    return jsonable(payload)
