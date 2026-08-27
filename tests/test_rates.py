"""
test_rates.py — Unit tests for rate resolution and half-up rounding precision.
"""
import pytest
from ledgerscope.rates import (
    round_half_up,
    applicable_rate_bps,
    GST_RATE_BPS,
    DEFAULT_RATE_BPS,
    INTERNATIONAL_RATE_BPS,
    RUPAY_UPI_CREDIT_RATE_BPS,
)
from ledgerscope.models import Transaction, FeePlan


def test_round_half_up_positive_half_integers():
    """Verify half-up rounding matches Indian accounting rules across odd and even boundaries."""
    # 480.5 paise: Banker's rounding rounds to 480 (even), Half-Up must round to 481
    assert round_half_up(4805, 10) == 481
    # 481.5 paise: Both round to 482
    assert round_half_up(4815, 10) == 482
    # 482.5 paise: Banker's rounding rounds to 482 (even), Half-Up must round to 483
    assert round_half_up(4825, 10) == 483


def test_round_half_up_exact_integers():
    assert round_half_up(1000, 10) == 100
    assert round_half_up(0, 10) == 0


def test_round_half_up_zero_division():
    with pytest.raises(ZeroDivisionError):
        round_half_up(100, 0)


def test_applicable_rate_precedence():
    plan = FeePlan(
        fee_plan_id="PLN_TEST",
        default_rate_bps=200,
        overrides={"netbanking": 190, "international": 300, "rupay_upi_credit": 215},
    )

    # 1. Default method
    txn_card = Transaction(
        txn_id="T1", merchant_id="M1", fee_plan_id="PLN_TEST",
        amount_paise=10000, currency="INR", payment_method="card",
        card_network=None, is_international=False, captured_at="2026-08-20T10:00:00Z"
    )
    assert applicable_rate_bps(txn_card, plan) == 200

    # 2. Method override
    txn_nb = Transaction(
        txn_id="T2", merchant_id="M1", fee_plan_id="PLN_TEST",
        amount_paise=10000, currency="INR", payment_method="netbanking",
        card_network=None, is_international=False, captured_at="2026-08-20T10:00:00Z"
    )
    assert applicable_rate_bps(txn_nb, plan) == 190

    # 3. International override
    txn_intl = Transaction(
        txn_id="T3", merchant_id="M1", fee_plan_id="PLN_TEST",
        amount_paise=10000, currency="INR", payment_method="card",
        card_network=None, is_international=True, captured_at="2026-08-20T10:00:00Z"
    )
    assert applicable_rate_bps(txn_intl, plan) == 300

    # 4. RuPay Credit on UPI override
    txn_rupay_upi = Transaction(
        txn_id="T4", merchant_id="M1", fee_plan_id="PLN_TEST",
        amount_paise=10000, currency="INR", payment_method="upi",
        card_network="rupay", is_international=False, captured_at="2026-08-20T10:00:00Z",
        is_credit_on_upi=True
    )
    assert applicable_rate_bps(txn_rupay_upi, plan) == 215
