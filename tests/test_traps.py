import csv
import io

import pytest

from app.catalog import SPEC
from app.errors import DomainIssue
from app.intake.normalize import canonical
from app.intake.service import load
from tests.domain_cases import row

# TRAP-02 TRAP-03 TRAP-04 TRAP-05 TRAP-06 TRAP-07 TRAP-08 TRAP-14 TRAP-16 TRAP-18 TRAP-22 TRAP-26


def make(tmp_path, body, name="case.csv", header=True):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    if header:
        writer.writerow(SPEC["columns"])
    for values in body:
        writer.writerow(values)
    path = tmp_path / name
    path.write_text(stream.getvalue(), encoding="utf-8")
    return path


def values(**changes):
    item = row()
    item.update(changes)
    return [item.get(column, "") for column in SPEC["columns"]]


def test_bom_is_removed():
    assert load("dirty")["sha256"]


def test_quoted_newline_is_one_record(tmp_path):
    path = make(tmp_path, [values(**{SPEC["columns"][1]: "A\nB"})], name="quote.csv")
    data = load("clean", str(path))
    assert data["counts"]["accepted"] == 1
    assert "\n" in data["rows"][0][SPEC["columns"][1]]


def test_repeated_header_is_ignored(tmp_path):
    path = tmp_path / "repeat.csv"
    path.write_text(",".join(SPEC["columns"]) + "\n" + ",".join(values()) + "\n" + ",".join(SPEC["columns"]) + "\n", encoding="utf-8")
    assert load("clean", str(path))["counts"]["ignored"] == 1


def test_extra_column_is_isolated(tmp_path):
    assert load("clean", str(make(tmp_path, [values() + ["extra"]])))["counts"]["isolated"] == 1


def test_fullwidth_digits_are_canonical():
    assert canonical("１２３") == "123"


def test_sentinel_is_blank():
    assert canonical("-") == ""


def test_leading_zero_is_preserved(tmp_path):
    item = row(**{SPEC["key"]: "0001"})
    data = load("clean", str(make(tmp_path, [[item.get(column, "") for column in SPEC["columns"]]])))
    assert data["rows"][0][SPEC["key"]] == "0001"


def test_conflicting_duplicate_is_isolated(tmp_path):
    field = next(field for field, kind in SPEC["types"].items() if kind not in {"date", "date_optional", "datetime"})
    path = tmp_path / "conflict.csv"
    path.write_text(",".join(SPEC["columns"]) + "\n" + ",".join(values()) + "\n" + ",".join(values(**{field: "999999"})) + "\n", encoding="utf-8")
    assert any(issue["code"] == "CONFLICT_DUPLICATE" for issue in load("clean", str(path))["issues"])


def test_unclosed_quote_rejects_file(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(",".join(SPEC["columns"]) + '\n"unclosed', encoding="utf-8")
    with pytest.raises(DomainIssue):
        load("clean", str(path))


def test_empty_and_header_only_differ(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_bytes(b"")
    header = tmp_path / "header.csv"
    header.write_text(",".join(SPEC["columns"]) + "\n", encoding="utf-8")
    with pytest.raises(DomainIssue) as first:
        load("clean", str(empty))
    with pytest.raises(DomainIssue) as second:
        load("clean", str(header))
    assert first.value.code != second.value.code
