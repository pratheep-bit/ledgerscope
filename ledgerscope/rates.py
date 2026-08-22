"""
RATE BASIS
Source:          https://razorpay.com/pricing/  (fetched directly, not recalled)
Effective date:  Not published on the page. Treated as "current as of fetch."
MDR assumption:  2% platform fee, flat, across cards / UPI / netbanking / wallets.
                 Page states verbatim: "Razorpay charges 2% + GST per transaction."
                 Zero MDR on standard bank-to-bank UPI and RuPay debit, BUT the
                 2% platform fee still applies to those modes.
                 CONFIRMED: RuPay Credit Card on UPI carries a distinct platform
                 fee of 2.15% + GST — verbatim from the pricing page. Modeled as
                 its own override, not folded into the 2% default.
                 International cards at 3%: ASSUMED FOR THIS BUILD - not shown on
                 the fetched page. VERIFY BEFORE SUBMISSION.
                 Negotiated sub-2% plans: ASSUMED FOR THIS BUILD.
GST assumption:  18% on the platform fee (NOT on transaction principal).
                 ASSUMED FOR THIS BUILD - the pricing page says "+ GST" without
                 naming a percentage. VERIFY BEFORE SUBMISSION.
Verified on:     2026-08-22

Everything is integer paise and integer basis points. No float ever touches a
monetary value; floats appear only in deviation ratios, which are diagnostic
and never summed into money.
"""
from decimal import Decimal, ROUND_HALF_UP

GST_RATE_BPS = 1800              # 18.00% - ASSUMED, see RATE BASIS
DEFAULT_RATE_BPS = 200            # 2.00%  - per fetched pricing page
INTERNATIONAL_RATE_BPS = 300      # 3.00%  - ASSUMED, see RATE BASIS
RUPAY_UPI_CREDIT_RATE_BPS = 215   # 2.15%  - CONFIRMED, per fetched pricing page


def round_half_up(numerator: int, denominator: int) -> int:
    """Exact half-up rounding on integers. No float, no banker's rounding.

    Python's round() is banker's rounding: round(0.5)==0, round(1.5)==2. Indian
    financial convention is half-up. On a GST line that lands on exactly .50
    paise - which happens constantly, since 18% of a 2% fee produces .5 endings
    at a predictable cadence - the two conventions differ by one paise. That one
    paise, repeated across a settlement batch, is exactly the E04 signal this
    engine is built to detect. Getting it wrong here would make the engine
    manufacture the very defect it claims to find.
    """
    return int((Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def applicable_rate_bps(txn, fee_plan) -> int:
    """Resolve the fee rate for one transaction. Deterministic lookup only.

    Precedence: RuPay-UPI-credit special case > plan method-specific override >
    international > plan default > system default. A misconfigured override is
    the single most likely real-world root cause - the whole point of this
    system is to find it, not to reproduce it, so precedence must be explicit.
    """
    if (txn.payment_method == "upi" and txn.card_network == "rupay"
            and getattr(txn, "is_credit_on_upi", False)):
        return fee_plan.overrides.get("rupay_upi_credit", RUPAY_UPI_CREDIT_RATE_BPS)
    if txn.is_international:
        return fee_plan.overrides.get("international", INTERNATIONAL_RATE_BPS)
    return fee_plan.overrides.get(txn.payment_method, fee_plan.default_rate_bps)
