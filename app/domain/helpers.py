from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.intake.normalize import canonical


def D(value, code="BAD_NUMBER"):
    text = canonical(value)
    if text == "":
        raise ValueError(code)
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        raise ValueError(code)


def I(value, code="BAD_INTEGER"):
    number = D(value, code)
    if number != number.to_integral_value():
        raise ValueError(code)
    return int(number)


def M(value, code="BAD_MONEY"):
    return int((D(value, code) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def TS(value, code="BAD_DATETIME"):
    text = canonical(value)
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    raise ValueError(code)


def DAY(value, code="BAD_DATE"):
    text = canonical(value)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(code)


def optional(kind, value, code):
    if value is None or canonical(value) == "":
        return None
    return kind(value, code)


def round_div(numerator: int, denominator: int) -> int:
    return int((numerator + denominator // 2) // denominator)


def largest_remainder(total, weights):
    total = int(total)
    weights = [int(weight) for weight in weights]
    denominator = sum(weights)
    if denominator <= 0:
        return [total] + [0] * (len(weights) - 1)
    base = [total * weight // denominator for weight in weights]
    remaining = total - sum(base)
    order = sorted(range(len(weights)), key=lambda idx: (-(total * weights[idx] % denominator), idx))
    for idx in order[:remaining]:
        base[idx] += 1
    return base


def business_days_after(start: date, count: int, holidays: set[date]) -> date:
    cursor = start
    remaining = count
    while remaining > 0:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor not in holidays:
            remaining -= 1
    return cursor


def tier_fee(days: int) -> int:
    if days <= 0:
        return 0
    first = min(days, 3) * 8000
    second = min(max(days - 3, 0), 5) * 14000
    third = max(days - 8, 0) * 22000
    return first + second + third


def roll_business_deadline(value: datetime, holidays: set[date]) -> datetime:
    cursor = value
    while cursor.weekday() >= 5 or cursor.date() in holidays:
        cursor += timedelta(days=1)
    return cursor


def business_hours_between(start: datetime, end: datetime, holidays: set[date]) -> int:
    if end <= start:
        return 0
    total = 0.0
    cursor = start.date()
    while cursor <= end.date():
        if cursor.weekday() < 5 and cursor not in holidays:
            opens = datetime.combine(cursor, time(8, 0))
            closes = datetime.combine(cursor, time(18, 0))
            left = max(start, opens)
            right = min(end, closes)
            total += max(0.0, (right - left).total_seconds() / 3600)
        cursor += timedelta(days=1)
    return int(total)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = value.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)
