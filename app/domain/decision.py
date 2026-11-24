from app.domain.helpers import D


def decide_rows(items):
    for item in items:
        if item["action"] == "REFUND" and item["invoice_cents"] > 0:
            item["verdict"] = "REJECT"
            item["reason"] = "REFUND_DIRECTION"
        elif item["invoice_cents"] != item["settlement_cents"]:
            item["verdict"] = "REVIEW"
            item["reason"] = "SETTLEMENT_MISMATCH"
        elif item["action"] == "REFUND" and item["settlement_cents"] >= 0 and item["original_fare_cents"] > 0:
            item["verdict"] = "REJECT"
            item["reason"] = "NEGATIVE_REFUND"
        else:
            item["verdict"] = "PASS"
            item["reason"] = "SETTLEMENT_OK"
        item.setdefault("verdict", "PASS")
        item.setdefault("reason", "OK")
    return items
