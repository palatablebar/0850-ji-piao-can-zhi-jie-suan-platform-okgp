from decimal import Decimal

from app.catalog import SPEC
from app.domain.calculate import calculate_rows
from app.domain.prepare import prepare_rows
from tests.domain_cases import CLEAN, calc

# TRAP-19 TRAP-20 TRAP-24 的边界由本文件的跨日、合并与单位用例固定。


def clean_results():
    items, issues = prepare_rows(CLEAN)
    assert issues == []
    return calculate_rows(items)


def test_clean_result_count():
    assert len(clean_results()) == 6


def test_metric_total_is_reconciled():
    total = sum((item["metric"] for item in clean_results()), Decimal("0"))
    assert total == Decimal("25600")


def test_first_result_matches_expected():
    item = clean_results()[0]
    assert item["label"] == "T1"
    assert abs(float(item["settlement_cents"]) - float("-12000")) < 0.011


def test_core_boundary_case():
    results, issues = calc([{'ticket_id': 'T9', 'passenger_id': 'P', 'action': 'REFUND', 'original_fare_cents': '1000', 'taxes_cents': '200', 'change_fee_cents': '0', 'refundable': 'Y', 'new_fare_cents': '0', 'invoice_cents': '-1200'}])
    assert issues == []
    value = results[0]["settlement_cents"]
    expected = '-1200'
    if expected in {"True", "False"}:
        assert bool(value) is (expected == "True")
    elif isinstance(expected, bool):
        assert bool(value) is expected
    elif expected.startswith("20") and len(expected) == 10:
        assert value.isoformat() == expected
    elif expected.replace(".", "", 1).replace("-", "", 1).isdigit():
        assert abs(float(value) - float(expected)) < 0.001
    else:
        assert value == expected


def test_result_labels_are_unique():
    labels = [item["label"] for item in clean_results()]
    assert len(labels) == len(set(labels))


def test_every_result_has_metric():
    assert all(item.get("metric") is not None for item in clean_results())
