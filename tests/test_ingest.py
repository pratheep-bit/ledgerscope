"""
test_ingest.py — Unit tests for data loading, boolean parsing, and inner join logic.
"""
import pytest
from pathlib import Path
from ledgerscope.ingest import _parse_bool, _require, join, load_fee_plans
from ledgerscope.models import Transaction, Settlement, FeePlan


def test_parse_bool():
    assert _parse_bool("true") is True
    assert _parse_bool("True") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True
    assert _parse_bool("false") is False
    assert _parse_bool("False") is False
    assert _parse_bool("0") is False
    assert _parse_bool("no") is False
    assert _parse_bool("") is False

    with pytest.raises(ValueError):
        _parse_bool("invalid_bool")


def test_require_field():
    row = {"txn_id": "T1", "amount": "100"}
    assert _require(row, "txn_id", "test.csv") == "T1"

    with pytest.raises(ValueError):
        _require(row, "missing_field", "test.csv")


def test_join_clean_and_orphans():
    txns = [
        Transaction("T1", "M1", "P1", 1000, "INR", "card", None, False, "2026-08-20T10:00:00Z"),
        Transaction("T2", "M1", "P1", 2000, "INR", "card", None, False, "2026-08-20T10:00:00Z"),
        Transaction("T3_ORPHAN", "M1", "P1", 3000, "INR", "card", None, False, "2026-08-20T10:00:00Z"),
    ]
    stls = [
        Settlement("S1", "T1", "B1", "2026-08-21T10:00:00Z", 1000, 20, 4, 976),
        Settlement("S2", "T2", "B1", "2026-08-21T10:00:00Z", 2000, 40, 7, 1953),
        Settlement("S4_ORPHAN", "T4_UNKNOWN", "B1", "2026-08-21T10:00:00Z", 4000, 80, 14, 3906),
    ]

    joined, txn_orphans, stl_orphans = join(txns, stls)

    assert len(joined) == 2
    assert [t.txn_id for t, _ in joined] == ["T1", "T2"]
    assert len(txn_orphans) == 1
    assert txn_orphans[0].txn_id == "T3_ORPHAN"
    assert len(stl_orphans) == 1
    assert stl_orphans[0].txn_id == "T4_UNKNOWN"
