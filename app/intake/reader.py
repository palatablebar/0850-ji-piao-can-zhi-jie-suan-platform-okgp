import csv
import io

from app.errors import DomainIssue
from app.intake.normalize import canonical
from app.intake.schema import validate_header


def decode(raw: bytes) -> str:
    if not raw:
        raise DomainIssue("EMPTY_FILE")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DomainIssue("HEADER_MISMATCH", detail="文件编码无法识别")


def read_records(raw: bytes, expected_columns, max_rows: int):
    if len(raw) == 0:
        raise DomainIssue("EMPTY_FILE")
    text = decode(raw)
    if not text.strip():
        raise DomainIssue("BLANK_FILE")
    stream = io.StringIO(text, newline="")
    try:
        parsed = list(csv.reader(stream, strict=True))
    except csv.Error:
        raise DomainIssue("UNCLOSED_QUOTE")
    if not parsed:
        raise DomainIssue("EMPTY_FILE")
    header = validate_header(parsed[0], expected_columns)
    body = parsed[1:]
    if not body or all(not any(cell.strip() for cell in row) for row in body):
        raise DomainIssue("HEADER_ONLY")
    if len(body) > max_rows:
        raise DomainIssue("TOO_MANY_ROWS")
    records = []
    for raw_row in body:
        row = [canonical(cell) for cell in raw_row]
        blank = not any(row)
        repeated = not blank and row == header
        records.append({"cells": row, "line": len(records) + 2, "blank": blank, "repeated": repeated})
    if not any(not record["blank"] and not record["repeated"] for record in records):
        raise DomainIssue("HEADER_ONLY")
    return {"header": header, "records": records}
