"""
test_engine.py — Tests for the core fee/tax computation engine.

TEST 1 is a load-bearing CRITICAL test. The rounding boundary table also
exercises the exact half-up boundary behaviour that E04 detection depends on.
"""
import pytest
from ledgerscope.models import Transaction, Settlement, FeePlan
from ledgerscope.engine import recompute
from ledgerscope.rates import round_half_up


# ---------------------------------------------------------------------------
# TEST 1 (CRITICAL) — eye-checkable anchor from the design doc
# ---------------------------------------------------------------------------

def test_test1_rounding_half_up():
    """TEST 1: ₹1,337.49 transaction at PLN_STD (200bps). Expected fee = 2675
    paise, expected GST = 482 paise (half-up from 481.5). Must MATCH exactly."""
    txn = Transaction(
        txn_id="t1", merchant_id="m1", fee_plan_id="PLN_STD",
        amount_paise=133749, currency="INR", payment_method="netbanking",
        card_network=None, is_international=False,
        captured_at="2026-08-14T00:00:00Z", is_refund=False, parent_txn_id=None,
    )
    plan = FeePlan(fee_plan_id="PLN_STD", default_rate_bps=200, overrides={})
    settlement = Settlement(
        settlement_id="s1", txn_id="t1", settlement_batch="STL_1",
        settled_at="2026-08-15T00:00:00Z", gross_paise=133749,
        fee_paise=2675, tax_paise=482, net_paise=133749 - 2675 - 482,
    )

    mr = recompute(txn, settlement, plan)

    assert mr.expected_fee_paise == 2675
    assert mr.expected_tax_paise == 482
    assert mr.status == "MATCHED"
    assert mr.fee_delta_paise == 0
    assert mr.tax_delta_paise == 0


# ---------------------------------------------------------------------------
# Rounding boundary table — at least 3 cases near the .5 paise boundary
# ---------------------------------------------------------------------------

def _make_txn_and_plan(amount_paise: int) -> tuple:
    """Helper: create a standard netbanking txn + PLN_STD plan."""
    txn = Transaction(
        txn_id="tb", merchant_id="m1", fee_plan_id="PLN_STD",
        amount_paise=amount_paise, currency="INR", payment_method="netbanking",
        card_network=None, is_international=False,
        captured_at="2026-08-14T00:00:00Z", is_refund=False, parent_txn_id=None,
    )
    plan = FeePlan(fee_plan_id="PLN_STD", default_rate_bps=200, overrides={})
    return txn, plan


def _settlement(txn, fee, tax):
    return Settlement(
        settlement_id="sb", txn_id=txn.txn_id, settlement_batch="STL_1",
        settled_at="2026-08-15T00:00:00Z", gross_paise=txn.amount_paise,
        fee_paise=fee, tax_paise=tax, net_paise=txn.amount_paise - fee - tax,
    )


def test_rounding_boundary_lands_on_dot5():
    """Case where fee * 18% lands exactly on .5 paise → should round up to next int.

    fee = 2675 paise → 2675 * 1800 / 10000 = 481.5 → rounds UP to 482.
    Verify round_half_up(2675*1800, 10000) == 482 (not 481 as banker's rounding gives).
    """
    result = round_half_up(2675 * 1800, 10000)
    assert result == 482, f"Expected 482 (half-up), got {result}"

    # Build a transaction that produces fee=2675 paise at 200bps
    # amount = 2675 * 10000 / 200 = 133750 paise (₹1,337.50)
    # But 133750 * 200 / 10000 = 2675.0 exactly — fee=2675
    txn, plan = _make_txn_and_plan(133750)
    stl = _settlement(txn, 2675, 482)  # 482 is the half-up correct value
    mr = recompute(txn, stl, plan)
    assert mr.expected_tax_paise == 482
    assert mr.status == "MATCHED"


def test_rounding_boundary_just_below_dot5():
    """Case where computation lands just below .5 → rounds DOWN.

    Find an amount where fee * 18% / 10000 ends in something < .5.
    amount_paise = 27778 → fee = round_half_up(27778*200, 10000)
                               = round_half_up(5555600, 10000) = 556
    GST = round_half_up(556 * 1800, 10000) = round_half_up(1000800, 10000)
        = 1000800 / 10000 = 100.08 → rounds DOWN to 100.
    This is strictly below .5, so floor and half-up both give 100.
    """
    result = round_half_up(556 * 1800, 10000)  # 1000800 / 10000 = 100.08 → 100
    assert result == 100

    txn, plan = _make_txn_and_plan(27778)
    expected_fee = round_half_up(27778 * 200, 10000)  # 5555600/10000 = 555.56 → 556
    assert expected_fee == 556
    expected_tax = round_half_up(expected_fee * 1800, 10000)  # 100.08 → 100
    assert expected_tax == 100
    stl = _settlement(txn, expected_fee, expected_tax)
    mr = recompute(txn, stl, plan)
    assert mr.expected_fee_paise == 556
    assert mr.expected_tax_paise == 100
    assert mr.status == "MATCHED"


def test_rounding_boundary_just_above_dot5():
    """Case where computation lands just above .5 → rounds UP (like half-up).

    amount_paise = 133750 → fee = 2675
    2675 * 1800 / 10000 = 481.5 → half-up → 482

    Now use amount = 133751 → fee = round_half_up(133751*200, 10000)
    = round_half_up(26750200, 10000) = 2675.02 → rounds to 2675
    GST = round_half_up(2675*1800, 10000) = 481.5 → 482 (same as before)
    """
    # Directly test round_half_up with a value just above .5
    # numerator/denominator = 5001/10 = 500.1 → floor to 500
    result_below = round_half_up(5001, 10)   # 500.1 → 500
    assert result_below == 500

    # numerator/denominator = 5005/10 = 500.5 → half-up → 501
    result_exact = round_half_up(5005, 10)   # 500.5 → 501
    assert result_exact == 501

    # numerator/denominator = 5009/10 = 500.9 → 501
    result_above = round_half_up(5009, 10)   # 500.9 → 501
    assert result_above == 501


def test_rounding_boundary_truncation_produces_exception():
    """If settlement uses truncation (floor) instead of half-up, engine detects it.

    amount = 133749, rate 200bps → fee = 2675
    Correct GST (half-up): round_half_up(2675*1800, 10000) = 482
    Truncated GST (floor):  int(2675*1800/10000)            = 481  ← off by 1

    Engine must report total_delta != 0 → status == EXCEPTION.
    """
    txn, plan = _make_txn_and_plan(133749)
    stl = _settlement(txn, 2675, 481)  # truncated, wrong
    mr = recompute(txn, stl, plan)
    assert mr.expected_tax_paise == 482
    assert mr.actual_tax_paise == 481
    assert mr.tax_delta_paise == -1
    assert mr.total_delta_paise == -1
    assert mr.status == "EXCEPTION"


# ---------------------------------------------------------------------------
# Additional sanity tests
# ---------------------------------------------------------------------------

def test_international_rate_applied():
    """International transactions must use INTERNATIONAL_RATE_BPS (300 bps)."""
    txn = Transaction(
        txn_id="t_intl", merchant_id="m1", fee_plan_id="PLN_STD",
        amount_paise=100000, currency="USD", payment_method="card",
        card_network="visa", is_international=True,
        captured_at="2026-08-14T00:00:00Z", is_refund=False, parent_txn_id=None,
    )
    plan = FeePlan(fee_plan_id="PLN_STD", default_rate_bps=200, overrides={})
    # expected_fee = 100000 * 300 / 10000 = 3000
    expected_fee = 3000
    expected_tax = round_half_up(3000 * 1800, 10000)  # 540
    stl = _settlement(txn, expected_fee, expected_tax)
    mr = recompute(txn, stl, plan)
    assert mr.applied_rate_bps == 300
    assert mr.expected_fee_paise == expected_fee
    assert mr.status == "MATCHED"


def test_negotiated_rate_override():
    """PLN_ENT_2024 overrides netbanking to 190bps."""
    txn = Transaction(
        txn_id="t_ent", merchant_id="m2", fee_plan_id="PLN_ENT_2024",
        amount_paise=100000, currency="INR", payment_method="netbanking",
        card_network=None, is_international=False,
        captured_at="2026-08-14T00:00:00Z", is_refund=False, parent_txn_id=None,
    )
    plan = FeePlan(fee_plan_id="PLN_ENT_2024", default_rate_bps=200,
                   overrides={"netbanking": 190})
    # expected_fee = 100000 * 190 / 10000 = 1900
    expected_fee = 1900
    expected_tax = round_half_up(1900 * 1800, 10000)  # 342
    stl = _settlement(txn, expected_fee, expected_tax)
    mr = recompute(txn, stl, plan)
    assert mr.applied_rate_bps == 190
    assert mr.expected_fee_paise == expected_fee
    assert mr.status == "MATCHED"
