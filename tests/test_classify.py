"""
test_classify.py — One test per exception code E01, E03, E04, E05, E06, E09.

Each test constructs a minimal txn/settlement/mr combination that triggers
exactly that code, and asserts classify() returns it.
"""
import dataclasses
import pytest
from ledgerscope.models import Transaction, Settlement, FeePlan, MatchResult
from ledgerscope.engine import recompute
from ledgerscope.classify import classify
from ledgerscope.rates import round_half_up, GST_RATE_BPS, DEFAULT_RATE_BPS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _std_plan():
    return FeePlan(fee_plan_id="PLN_STD", default_rate_bps=200, overrides={})


def _ent_plan():
    return FeePlan(fee_plan_id="PLN_ENT_2024", default_rate_bps=200,
                   overrides={"netbanking": 190})


def _base_txn(**kwargs):
    defaults = dict(
        txn_id="T001", merchant_id="M1", fee_plan_id="PLN_STD",
        amount_paise=100000, currency="INR", payment_method="card",
        card_network="visa", is_international=False,
        captured_at="2026-08-14T00:00:00Z", is_refund=False, parent_txn_id=None,
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _base_stl(txn, **kwargs):
    defaults = dict(
        settlement_id="S001", txn_id=txn.txn_id, settlement_batch="STL_1",
        settled_at="2026-08-15T00:00:00Z", gross_paise=txn.amount_paise,
        fee_paise=2000, tax_paise=360, net_paise=txn.amount_paise - 2000 - 360,
    )
    defaults.update(kwargs)
    return Settlement(**defaults)


def _run(txn, stl, plan):
    """Run recompute then classify, returning (mr_with_codes, code, rule)."""
    mr = recompute(txn, stl, plan)
    code, rule = classify(mr, txn, stl)
    mr = dataclasses.replace(mr, exception_code=code, rule_fired=rule)
    return mr, code, rule


# ---------------------------------------------------------------------------
# E01 — FEE_RATE_MISMATCH
# ---------------------------------------------------------------------------

def test_classify_e01_fee_rate_mismatch():
    """PLN_ENT_2024 netbanking at 190bps; settlement charges 200bps → E01."""
    txn = _base_txn(fee_plan_id="PLN_ENT_2024", payment_method="netbanking",
                    card_network=None, amount_paise=100000)
    plan = _ent_plan()

    # Correct would be 190bps = 1900 fee; settlement charges 200bps = 2000
    stl = _base_stl(txn, fee_paise=2000,
                    tax_paise=round_half_up(2000 * GST_RATE_BPS, 10_000),
                    net_paise=100000 - 2000 - round_half_up(2000 * GST_RATE_BPS, 10_000))

    mr, code, rule = _run(txn, stl, plan)
    assert code == "E01", f"Expected E01, got {code}: {rule}"
    assert "implied" in rule


# ---------------------------------------------------------------------------
# E03 — GST_BASE_MISMATCH
# ---------------------------------------------------------------------------

def test_classify_e03_gst_base_mismatch():
    """Settlement computes tax as 18% of gross (100000) instead of 18% of fee (2000) → E03."""
    txn = _base_txn(amount_paise=100000)
    plan = _std_plan()

    correct_fee = round_half_up(100000 * DEFAULT_RATE_BPS, 10_000)  # 2000
    bad_tax     = round_half_up(100000 * GST_RATE_BPS, 10_000)      # 18000 — 18% of gross!
    stl = _base_stl(txn, fee_paise=correct_fee, tax_paise=bad_tax,
                    net_paise=100000 - correct_fee - bad_tax)

    mr, code, rule = _run(txn, stl, plan)
    assert code == "E03", f"Expected E03, got {code}: {rule}"


# ---------------------------------------------------------------------------
# E04 — ROUNDING_DRIFT
# ---------------------------------------------------------------------------

def test_classify_e04_rounding_drift():
    """GST truncated (481 instead of 482 half-up) on ₹1,337.49 → E04."""
    txn = _base_txn(amount_paise=133749, payment_method="netbanking", card_network=None)
    plan = _std_plan()

    fee    = round_half_up(133749 * DEFAULT_RATE_BPS, 10_000)  # 2675
    bad_tax = int(fee * GST_RATE_BPS / 10_000)                  # 481 (truncated)
    # Verify we've created the right test: correct is 482, truncated is 481
    assert round_half_up(fee * GST_RATE_BPS, 10_000) == 482
    assert bad_tax == 481

    stl = _base_stl(txn, fee_paise=fee, tax_paise=bad_tax,
                    net_paise=133749 - fee - bad_tax)

    mr, code, rule = _run(txn, stl, plan)
    assert code == "E04", f"Expected E04, got {code}: {rule}"
    assert "rounding" in rule.lower()


# ---------------------------------------------------------------------------
# E05 — MISSING_TAX_LINE
# ---------------------------------------------------------------------------

def test_classify_e05_missing_tax_line():
    """tax_paise is None while fee_paise > 0 → E05."""
    txn = _base_txn(amount_paise=50000, payment_method="upi", card_network=None)
    plan = _std_plan()

    fee = round_half_up(50000 * DEFAULT_RATE_BPS, 10_000)  # 1000
    stl = _base_stl(txn, fee_paise=fee, tax_paise=None,
                    net_paise=50000 - fee)

    mr, code, rule = _run(txn, stl, plan)
    assert code == "E05", f"Expected E05, got {code}: {rule}"
    assert "absent" in rule.lower()


# ---------------------------------------------------------------------------
# E06 — REFUND_FEE_NOT_REVERSED
# ---------------------------------------------------------------------------

def test_classify_e06_refund_fee_not_reversed():
    """is_refund=True; settlement charges a fee (positive) → E06."""
    txn = _base_txn(amount_paise=50000, is_refund=True, parent_txn_id="T000")
    plan = _std_plan()

    wrong_fee = round_half_up(50000 * DEFAULT_RATE_BPS, 10_000)  # 1000
    wrong_tax = round_half_up(wrong_fee * GST_RATE_BPS, 10_000)   # 180
    stl = _base_stl(txn, fee_paise=wrong_fee, tax_paise=wrong_tax,
                    net_paise=50000 - wrong_fee - wrong_tax)

    mr, code, rule = _run(txn, stl, plan)
    assert code == "E06", f"Expected E06, got {code}: {rule}"
    assert "refund" in rule.lower()


# ---------------------------------------------------------------------------
# E09 — UNEXPLAINED (residual catch-all)
# ---------------------------------------------------------------------------

def test_classify_e09_unexplained():
    """An exception that matches none of E01-E06/E08 should fall through to E09."""
    txn = _base_txn(amount_paise=100000)
    plan = _std_plan()

    # Construct a fee delta that is large (>2 paise) but rate looks correct from
    # implied_rate perspective, and fee/tax individually have weird deltas:
    # fee correct, tax off by an odd amount that doesn't match GST-on-gross or GST mismatch
    correct_fee = round_half_up(100000 * DEFAULT_RATE_BPS, 10_000)  # 2000
    correct_tax = round_half_up(correct_fee * GST_RATE_BPS, 10_000)  # 360
    # Manufacture a weird 5-paise extra on both fee AND tax — total >2 paise,
    # rates look correct (2000/100000 = 200bps exactly), but something is off
    weird_fee = correct_fee + 5
    weird_tax = correct_tax + 5

    stl = _base_stl(txn, fee_paise=weird_fee, tax_paise=weird_tax,
                    net_paise=100000 - weird_fee - weird_tax)

    mr, code, rule = _run(txn, stl, plan)
    # With weird_fee=2005: implied_rate = round_half_up(2005*10000, 100000) = 201bps
    # applied_rate = 200bps → |201-200|=1 ≤ 1 → does NOT trigger E01
    # total_delta = 10 > 2 → does NOT trigger E04
    # is_refund=False → skip E06
    # tax_paise=365 ≠ None/0 → skip E05
    # gst_on_gross = round_half_up(100000*1800,10000) = 18000 ≠ 365 → skip E03
    # fee_delta = 5 ≠ 0 → skip E02
    # Falls through → E09
    assert code == "E09", f"Expected E09, got {code}: {rule}"
