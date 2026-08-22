"""
engine.py — Core fee/tax recomputation. One function, no I/O, no randomness.

This is the credibility floor of the entire submission. If an LLM were computing
these numbers, nothing downstream would be worth reading.
"""
from .rates import GST_RATE_BPS, applicable_rate_bps, round_half_up
from .models import MatchResult


def recompute(txn, settlement, fee_plan) -> MatchResult:
    """The core arithmetic. Called once per transaction. No model, no network,
    no randomness, no clock. Same input -> same output, forever.

    This function is the credibility floor of the entire submission. If an LLM
    were computing these numbers, nothing downstream would be worth reading.
    """
    rate_bps = applicable_rate_bps(txn, fee_plan)

    expected_fee = round_half_up(txn.amount_paise * rate_bps, 10_000)
    expected_tax = round_half_up(expected_fee * GST_RATE_BPS, 10_000)

    actual_fee = settlement.fee_paise
    actual_tax = settlement.tax_paise if settlement.tax_paise is not None else 0

    fee_delta = actual_fee - expected_fee
    tax_delta = actual_tax - expected_tax
    total_delta = fee_delta + tax_delta

    expected_total = expected_fee + expected_tax
    deviation_ratio = (total_delta / expected_total) if expected_total else 0.0

    implied_rate_bps = (round_half_up(actual_fee * 10_000, txn.amount_paise)
                        if txn.amount_paise else None)

    return MatchResult(
        txn_id=txn.txn_id,
        status="MATCHED" if total_delta == 0 else "EXCEPTION",
        expected_fee_paise=expected_fee, actual_fee_paise=actual_fee,
        fee_delta_paise=fee_delta,
        expected_tax_paise=expected_tax, actual_tax_paise=settlement.tax_paise,
        tax_delta_paise=tax_delta, total_delta_paise=total_delta,
        deviation_ratio=deviation_ratio,
        exception_code=None, rule_fired=None,   # classify.py fills these in
        applied_rate_bps=rate_bps, implied_rate_bps=implied_rate_bps,
    )
