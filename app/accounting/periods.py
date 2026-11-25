import re
from datetime import date

from app.errors import DomainIssue

PERIOD_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def validate_period(period: str) -> str:
    text = "" if period is None else str(period).strip()
    if not PERIOD_RE.fullmatch(text):
        raise DomainIssue("BAD_PERIOD")
    return text


def current_period(today: date | None = None) -> str:
    day = today or date.today()
    return f"{day.year:04d}-{day.month:02d}"


def next_period(period: str) -> str:
    validate_period(period)
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{month + 1:02d}"
