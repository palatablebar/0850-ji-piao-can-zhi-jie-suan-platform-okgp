from decimal import Decimal

from app.catalog import SPEC
from app.service import pipeline
from tests.domain_cases import CLEAN


def payload():
    return pipeline("clean")


def test_source_rows_are_balanced():
    assert payload()["ledger"]["balanced"] is True


def test_counts_add_up():
    counts = payload()["counts"]
    assert counts["input"] == counts["accepted"] + counts["isolated"] + counts["duplicates"] + counts["ignored"]


def test_accepted_count_matches_sample():
    assert payload()["counts"]["accepted"] == 6


def test_computed_count_matches_rule():
    assert payload()["counts"]["computed"] == 6


def test_metric_total_matches_rows():
    data = payload()
    assert Decimal(data["ledger"]["metric_total"]) == Decimal("25600")


def test_ledger_checks_pass():
    assert all(item["ok"] for item in payload()["ledger"]["checks"])
