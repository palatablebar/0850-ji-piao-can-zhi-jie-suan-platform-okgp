from app.catalog import SPEC
from app.domain.helpers import D, DAY, I, M, TS, optional
from app.intake.normalize import canonical


PARSERS = {
    "money": lambda value, code: M(value, code),
    "decimal": lambda value, code: D(value, code),
    "decimal_optional": lambda value, code: optional(D, value, code),
    "int": lambda value, code: I(value, code),
    "int_positive": lambda value, code: positive(I(value, code)),
    "date": lambda value, code: DAY(value, code),
    "date_optional": lambda value, code: optional(DAY, value, code),
    "datetime": lambda value, code: TS(value, code),
}


def positive(value):
    if value <= 0:
        raise ValueError("BAD_POSITIVE")
    return value


def _typed(rows):
    typed, issues = [], []
    for raw in rows:
        item = dict(raw)
        try:
            if not canonical(item.get(SPEC["key"], "")):
                raise ValueError("KEY_MISSING")
            for field, kind in SPEC["types"].items():
                code = "INVALID_" + field.upper()
                item[field] = PARSERS[kind](item.get(field), code)
            typed.append(item)
        except ValueError as exc:
            issues.append({"line": raw.get("_line", 0), "key": raw.get(SPEC["key"], ""), "code": str(exc)})
    return typed, issues


def prepare_rows(rows):
    typed, issues = _typed(rows)
    rows = typed
    items = []
    for item in typed:
        try:
            if not canonical(item.get(SPEC["key"], "")):
                raise ValueError("KEY_MISSING")
            action = item["action"].upper()
            if action not in {"REFUND", "REISSUE"}:
                raise ValueError("BAD_ACTION")
            refundable = item["refundable"].upper()
            if refundable not in {"Y", "N"}:
                raise ValueError("BAD_REFUNDABLE")
            item["action"] = action
            item["refundable"] = refundable == "Y"
            if min(item["original_fare_cents"], item["taxes_cents"], item["change_fee_cents"], item["new_fare_cents"]) < 0:
                raise ValueError("BAD_AMOUNT")
            items.append(item)
        except ValueError as exc:
            issues.append({"line": item.get("_line", 0), "key": item.get(SPEC["key"], ""), "code": str(exc)})
    return items, issues
