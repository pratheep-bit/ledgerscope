"""
classify.py — Exception classification cascade (E01–E09).

Taxonomy is closed and ordered. First match wins. E09 (UNEXPLAINED) is always
reported for any exception that clears none of the prior rules — never suppressed.

Check E03 BEFORE E01/E02 — a base error also looks like a wildly wrong rate,
and would get misfiled as E01 otherwise.
"""
from .rates import GST_RATE_BPS, round_half_up


def classify(mr, txn, settlement) -> tuple:
    """Returns (exception_code, rule_fired). Order matters: the cascade runs
    most-specific to least, first match wins, and the residual is always
    reported rather than dropped.
    """
    if settlement.tax_paise in (None, 0) and settlement.fee_paise > 0:
        return "E05", "tax line absent while a fee was charged"

    if txn.is_refund and mr.fee_delta_paise >= 0:
        return "E06", "refund settled without reversing the original fee"

    gst_on_gross = round_half_up(settlement.gross_paise * GST_RATE_BPS, 10_000)
    if settlement.tax_paise and abs(settlement.tax_paise - gst_on_gross) <= 2:
        return "E03", "GST base is gross amount, expected platform fee"

    if abs(mr.total_delta_paise) <= 2 and mr.implied_rate_bps == mr.applied_rate_bps:
        return "E04", "sub-paise drift, rates correct: rounding convention"

    if mr.implied_rate_bps is not None and \
       abs(mr.implied_rate_bps - mr.applied_rate_bps) > 1:
        return "E01", (f"implied {mr.implied_rate_bps}bps != "
                       f"applied {mr.applied_rate_bps}bps")

    if mr.fee_delta_paise == 0 and mr.tax_delta_paise != 0:
        implied_gst = round_half_up(mr.actual_tax_paise * 10_000,
                                    mr.actual_fee_paise)
        if abs(implied_gst - GST_RATE_BPS) > 10:
            return "E02", f"implied GST {implied_gst}bps != {GST_RATE_BPS}bps"

    return "E09", "no classification rule matched"
