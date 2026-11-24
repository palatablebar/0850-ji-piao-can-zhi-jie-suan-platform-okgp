from app.catalog import SPEC
from app.service import pipeline


def test_catalog_has_seven_stages():
    assert len(SPEC["stages"]) == 7


def test_columns_include_key():
    assert SPEC["key"] in SPEC["columns"]
    assert len(SPEC["columns"]) >= 5


def test_dirty_sample_has_multiple_issue_classes():
    codes = {issue["code"] for issue in pipeline("dirty")["issues"]}
    assert len(codes) >= 3
