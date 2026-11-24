from decimal import Decimal

from app.catalog import SPEC
from app.reconcile.checks import all_checks


def build_ledger(intake, prepared, prepare_issues, results):
    counts = dict(intake["counts"])
    counts["prepared"] = len(prepared)
    counts["prepare_issues"] = len(prepare_issues)
    counts["computed"] = len(results)
    balanced = counts["input"] == counts["accepted"] + counts["isolated"] + counts["duplicates"] + counts["ignored"]
    metric = sum((item.get("metric") for item in results if item.get("metric") is not None), Decimal("0"))
    checks = [
        {"id": "source", "label": "来源行守恒", "ok": balanced},
        {"id": "computed", "label": "计算条目完整", "ok": counts["computed"] == len(results)},
    ]
    return {"counts": counts, "balanced": balanced, "metric_field": SPEC.get("metric_field", "metric"),
            "metric_total": str(metric), "checks": checks, "all_checks": all_checks(checks)}
