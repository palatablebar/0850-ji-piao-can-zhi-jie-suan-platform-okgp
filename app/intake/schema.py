from app.errors import DomainIssue
from app.intake.normalize import canonical


def normalize_header(cells):
    return [canonical(cell) for cell in cells]


def validate_header(header, expected):
    if normalize_header(header) != normalize_header(expected):
        raise DomainIssue("HEADER_MISMATCH")
    return normalize_header(header)
