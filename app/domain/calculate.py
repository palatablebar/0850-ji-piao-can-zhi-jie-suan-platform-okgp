from datetime import date, timedelta
from app.catalog import SPEC
from app.domain.helpers import *  # noqa: F401,F403


def calculate_rows(items):
    out = []
    rows = items
    for item in items:
        if item["action"] == "REFUND":
            amount = item["taxes_cents"] + (item["original_fare_cents"] if item["refundable"] else 0) - item["change_fee_cents"]
            settlement = -max(0, amount)
        else:
            credit = item["original_fare_cents"] if item["refundable"] else 0
            settlement = max(0, item["new_fare_cents"] - credit) + item["change_fee_cents"]
        item["settlement_cents"] = settlement
        item["metric"] = D(str(abs(settlement)), "CALC")
        item["limit"] = D(str(max(item["original_fare_cents"], item["new_fare_cents"]) + item["taxes_cents"]), "LIMIT")
        out.append(item)
    for item in out:
        item.setdefault("label", str(item.get(SPEC["key"], "")))
    return out
