"""
Ledgerscope data models.

All monetary values are integer paise. No float ever touches a monetary value.
Floats appear only in deviation_ratio and similar diagnostic ratios, and those
are never summed into a rupee amount.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    merchant_id: str
    fee_plan_id: str
    amount_paise: int
    currency: str
    payment_method: str          # "card" | "upi" | "netbanking" | "wallet"
    card_network: str | None     # "visa" | "mastercard" | "rupay" | "amex" | None
    is_international: bool
    captured_at: str             # ISO-8601 UTC string
    is_refund: bool = False
    parent_txn_id: str | None = None    # set only if is_refund is True
    # Extra field not in Step 2 schema — added deliberately to support the
    # RuPay Credit Card on UPI rate override (2.15%) in rates.py.
    # Documented in PROGRESS.md under "Known deviations from spec".
    is_credit_on_upi: bool = False


@dataclass(frozen=True)
class Settlement:
    settlement_id: str
    txn_id: str
    settlement_batch: str
    settled_at: str
    gross_paise: int
    fee_paise: int
    tax_paise: int | None        # None means the tax line is absent (feeds E05)
    net_paise: int


@dataclass(frozen=True)
class FeePlan:
    fee_plan_id: str
    default_rate_bps: int
    overrides: dict              # Key convention: payment_method string (e.g. "netbanking")
                                  # OR "international" for international card override
                                  # OR "rupay_upi_credit" for RuPay Credit Card on UPI (2.15%)
                                  # Use these key strings consistently in generate.py and rates.py.


@dataclass(frozen=True)
class MatchResult:
    txn_id: str
    status: str                  # "MATCHED" | "EXCEPTION" | "ORPHAN"
    expected_fee_paise: int
    actual_fee_paise: int
    fee_delta_paise: int
    expected_tax_paise: int
    actual_tax_paise: int | None
    tax_delta_paise: int
    total_delta_paise: int
    deviation_ratio: float
    exception_code: str | None
    rule_fired: str | None
    applied_rate_bps: int
    implied_rate_bps: int | None

    @property
    def is_matched(self) -> bool:
        """Returns True if the record settled with zero discrepancy."""
        return self.status == "MATCHED"

    @property
    def is_exception(self) -> bool:
        """Returns True if the record has a settlement discrepancy."""
        return self.status == "EXCEPTION"
