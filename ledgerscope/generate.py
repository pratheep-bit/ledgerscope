"""
generate.py — Produce the 62-record synthetic batch for testing and demonstration.

Run: python -m ledgerscope.generate [--seed 42] [--out-dir synthetic/]

Output:
  synthetic/transactions.csv
  synthetic/settlements.csv
  synthetic/fee_plans.json

Batch composition (exactly 62 rows, exactly 18 exceptions):
  44  Clean records            (MATCHED, PLN_STD 200bps)
  10  E01 FEE_RATE_MISMATCH    (PLN_ENT_2024 190bps netbanking; settlement charges 200bps)
   3  E04 ROUNDING_DRIFT       (GST truncated toward zero instead of half-up)
   2  E03 GST_BASE_MISMATCH    (tax computed on gross_paise, not fee_paise)
   2  E06 REFUND_FEE_NOT_REVERSED (is_refund=True; fee not credited back)
   1  E05 MISSING_TAX_LINE     (tax_paise is None while fee_paise > 0)
  --
  62  Total

E02, E07, E08 are intentionally unexercised in this batch — documented in README.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
from pathlib import Path

from .rates import round_half_up, DEFAULT_RATE_BPS, GST_RATE_BPS

# ---------------------------------------------------------------------------
# Fee plan definitions
# ---------------------------------------------------------------------------
FEE_PLANS = [
    {
        "fee_plan_id": "PLN_STD",
        "default_rate_bps": 200,
        "overrides": {},
    },
    {
        "fee_plan_id": "PLN_ENT_2024",
        "default_rate_bps": 200,
        "overrides": {"netbanking": 190},  # negotiated netbanking rate
    },
]

PAYMENT_METHODS = ["card", "upi", "netbanking", "wallet"]
CARD_NETWORKS   = ["visa", "mastercard", "rupay", "amex", None]
MERCHANTS       = ["M_ALPHA", "M_BETA", "M_GAMMA"]

# Deliberately awkward amounts (paise) that exercise the rounding path
AWKWARD_AMOUNTS = [
    133749,   # ₹1,337.49 — the canonical TEST 1 amount
    9999,     # ₹99.99
    250001,   # ₹2,500.01
    375050,   # ₹3,750.50
    88888,    # ₹888.88
    199999,   # ₹1,999.99
    55555,    # ₹555.55
    77777,    # ₹777.77
    123456,   # ₹1,234.56
    999950,   # ₹9,999.50
]

BATCH_ID      = "STL_2026_08"
CAPTURE_DATE  = "2026-08-14T{:02d}:{:02d}:{:02d}Z"
SETTLE_DATE_1 = "2026-08-15T00:00:00Z"
SETTLE_DATE_2 = "2026-08-16T00:00:00Z"
SETTLE_DATE_3 = "2026-08-17T00:00:00Z"


def _txn_id(i: int) -> str:
    return f"TXN_{i:04d}"


def _stl_id(i: int) -> str:
    return f"STL_{i:04d}"


def _capture_time(i: int) -> str:
    h = (i * 7) % 24
    m = (i * 13) % 60
    s = (i * 17) % 60
    return CAPTURE_DATE.format(h, m, s)


def _settle_date(i: int) -> str:
    """Distribute settlements across 3 days for a 3-day batch span."""
    day = i % 3
    return [SETTLE_DATE_1, SETTLE_DATE_2, SETTLE_DATE_3][day]


def _clean_record(i: int, rng: random.Random) -> tuple[dict, dict]:
    """Generate one perfectly clean matched record on PLN_STD."""
    amount = rng.choice(AWKWARD_AMOUNTS + [rng.randint(5000, 500000)])
    method = rng.choice(PAYMENT_METHODS)
    network = rng.choice(CARD_NETWORKS) if method == "card" else None

    fee  = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)
    tax  = round_half_up(fee * GST_RATE_BPS, 10_000)
    net  = amount - fee - tax

    txn = dict(
        txn_id=_txn_id(i), merchant_id=rng.choice(MERCHANTS),
        fee_plan_id="PLN_STD", amount_paise=amount,
        currency="INR", payment_method=method,
        card_network=network or "", is_international=False,
        captured_at=_capture_time(i), is_refund=False,
        parent_txn_id="", is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=fee, tax_paise=tax, net_paise=net,
    )
    return txn, stl


def _e01_record(i: int, rng: random.Random) -> tuple[dict, dict]:
    """E01 FEE_RATE_MISMATCH: PLN_ENT_2024 netbanking (190bps) but settlement
    applies 200bps — the same sign, near-identical deviation across all 10."""
    amount = rng.choice(AWKWARD_AMOUNTS + [rng.randint(50000, 300000)])

    correct_fee = round_half_up(amount * 190, 10_000)   # what the plan says
    wrong_fee   = round_half_up(amount * 200, 10_000)   # what settlement charges
    wrong_tax   = round_half_up(wrong_fee * GST_RATE_BPS, 10_000)
    net         = amount - wrong_fee - wrong_tax

    txn = dict(
        txn_id=_txn_id(i), merchant_id="M_ENT",
        fee_plan_id="PLN_ENT_2024", amount_paise=amount,
        currency="INR", payment_method="netbanking",
        card_network="", is_international=False,
        captured_at=_capture_time(i), is_refund=False,
        parent_txn_id="", is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=wrong_fee, tax_paise=wrong_tax, net_paise=net,
    )
    return txn, stl


def _e04_record(i: int, rng: random.Random) -> tuple[dict, dict]:
    """E04 ROUNDING_DRIFT: GST truncated (floor) instead of half-up.

    Pick amounts where half-up and floor differ by exactly 1 paise on the GST
    line — these are amounts where fee * 1800 / 10000 lands on .5 exactly.
    The canonical such amount is 133749 → fee=2675 → GST: 481.5 → half-up=482, floor=481.
    """
    # Amounts known to produce .5 GST boundary:
    # fee * 1800 mod 10000 == 5000  →  fee is odd multiple of 500/18 ...
    # Easiest: any amount where fee ends in ...25 or ...75 paise
    # (fee=2675 → 2675*1800=4815000 → 4815000/10000=481.5 ✓)
    E04_AMOUNTS = [133749, 133750, 277778]  # each gives a .5 GST boundary

    amount = E04_AMOUNTS[(i - 1) % len(E04_AMOUNTS)]
    fee = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)

    # Correctly computed tax (half-up)
    correct_tax = round_half_up(fee * GST_RATE_BPS, 10_000)
    # Truncated tax (floor, as a wrong settlement system would compute)
    truncated_tax = int(fee * GST_RATE_BPS / 10_000)

    # Only inject if they differ — if they don't, pick next amount
    if truncated_tax == correct_tax:
        amount = 133749  # fallback: this is guaranteed to differ
        fee = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)
        correct_tax = round_half_up(fee * GST_RATE_BPS, 10_000)
        truncated_tax = int(fee * GST_RATE_BPS / 10_000)

    net = amount - fee - truncated_tax

    txn = dict(
        txn_id=_txn_id(i), merchant_id=rng.choice(MERCHANTS),
        fee_plan_id="PLN_STD", amount_paise=amount,
        currency="INR", payment_method="netbanking",
        card_network="", is_international=False,
        captured_at=_capture_time(i), is_refund=False,
        parent_txn_id="", is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=fee, tax_paise=truncated_tax, net_paise=net,
    )
    return txn, stl


def _e03_record(i: int, rng: random.Random) -> tuple[dict, dict]:
    """E03 GST_BASE_MISMATCH: settlement computes tax as 18% of GROSS, not fee.

    This produces a ~55x overcharge on the tax line (gross is ~50x the fee at 2%).
    """
    amount = rng.choice([100000, 200000])  # ₹1000 or ₹2000 — easy to verify

    fee     = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)
    bad_tax = round_half_up(amount * GST_RATE_BPS, 10_000)  # 18% of GROSS (wrong)
    net     = amount - fee - bad_tax

    txn = dict(
        txn_id=_txn_id(i), merchant_id=rng.choice(MERCHANTS),
        fee_plan_id="PLN_STD", amount_paise=amount,
        currency="INR", payment_method="card",
        card_network="visa", is_international=False,
        captured_at=_capture_time(i), is_refund=False,
        parent_txn_id="", is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=fee, tax_paise=bad_tax, net_paise=net,
    )
    return txn, stl


def _e06_record(i: int, parent_i: int, rng: random.Random) -> tuple[dict, dict]:
    """E06 REFUND_FEE_NOT_REVERSED: is_refund=True; fee not credited back.

    The settlement charges a fee on the refund instead of reversing it.
    """
    amount = rng.choice([50000, 75000])

    # Wrong: settlement applies a fee on the refund (should be 0 or negative)
    wrong_fee = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)
    wrong_tax = round_half_up(wrong_fee * GST_RATE_BPS, 10_000)
    net       = amount - wrong_fee - wrong_tax

    txn = dict(
        txn_id=_txn_id(i), merchant_id=rng.choice(MERCHANTS),
        fee_plan_id="PLN_STD", amount_paise=amount,
        currency="INR", payment_method="card",
        card_network="visa", is_international=False,
        captured_at=_capture_time(i), is_refund=True,
        parent_txn_id=_txn_id(parent_i), is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=wrong_fee, tax_paise=wrong_tax, net_paise=net,
    )
    return txn, stl


def _e05_record(i: int, rng: random.Random) -> tuple[dict, dict]:
    """E05 MISSING_TAX_LINE: tax_paise is None (empty string in CSV) while fee > 0."""
    amount = 50000

    fee = round_half_up(amount * DEFAULT_RATE_BPS, 10_000)
    net = amount - fee  # no tax deducted

    txn = dict(
        txn_id=_txn_id(i), merchant_id=rng.choice(MERCHANTS),
        fee_plan_id="PLN_STD", amount_paise=amount,
        currency="INR", payment_method="upi",
        card_network="", is_international=False,
        captured_at=_capture_time(i), is_refund=False,
        parent_txn_id="", is_credit_on_upi=False,
    )
    stl = dict(
        settlement_id=_stl_id(i), txn_id=_txn_id(i),
        settlement_batch=BATCH_ID, settled_at=_settle_date(i),
        gross_paise=amount, fee_paise=fee, tax_paise="", net_paise=net,
        # tax_paise="" → parsed as None by ingest.py (feeds E05)
    )
    return txn, stl


def generate(seed: int = 42, out_dir: str | Path = "synthetic") -> None:
    """Generate the 62-record synthetic batch and write CSV + JSON files."""
    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    transactions = []
    settlements  = []
    counter      = [1]  # mutable so helpers can share it

    def next_i() -> int:
        val = counter[0]
        counter[0] += 1
        return val

    # 44 clean records
    for _ in range(44):
        txn, stl = _clean_record(next_i(), rng)
        transactions.append(txn)
        settlements.append(stl)

    # 10 E01 records
    for _ in range(10):
        txn, stl = _e01_record(next_i(), rng)
        transactions.append(txn)
        settlements.append(stl)

    # 3 E04 records
    for k in range(3):
        txn, stl = _e04_record(next_i(), rng)
        transactions.append(txn)
        settlements.append(stl)

    # 2 E03 records
    for _ in range(2):
        txn, stl = _e03_record(next_i(), rng)
        transactions.append(txn)
        settlements.append(stl)

    # 2 E06 records (parent_i doesn't need to match a real record — just informational)
    for k in range(2):
        txn, stl = _e06_record(next_i(), parent_i=k + 1, rng=rng)
        transactions.append(txn)
        settlements.append(stl)

    # 1 E05 record
    txn, stl = _e05_record(next_i(), rng)
    transactions.append(txn)
    settlements.append(stl)

    # ---------------------------------------------------------------------------
    # Assertions — validate composition before writing
    # ---------------------------------------------------------------------------
    total = len(transactions)
    assert total == 62, f"Expected 62 rows, got {total}"
    assert len(settlements) == 62, f"Expected 62 settlement rows, got {len(settlements)}"

    # Category counts
    categories = {
        "clean":  44,
        "e01":    10,
        "e04":     3,
        "e03":     2,
        "e06":     2,
        "e05":     1,
    }
    expected_total = sum(categories.values())
    assert expected_total == 62, f"Category sum {expected_total} != 62"

    # ---------------------------------------------------------------------------
    # Write files
    # ---------------------------------------------------------------------------
    txn_fields = [
        "txn_id", "merchant_id", "fee_plan_id", "amount_paise", "currency",
        "payment_method", "card_network", "is_international", "captured_at",
        "is_refund", "parent_txn_id", "is_credit_on_upi",
    ]
    stl_fields = [
        "settlement_id", "txn_id", "settlement_batch", "settled_at",
        "gross_paise", "fee_paise", "tax_paise", "net_paise",
    ]

    with (out_dir / "transactions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=txn_fields)
        w.writeheader()
        w.writerows(transactions)

    with (out_dir / "settlements.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=stl_fields)
        w.writeheader()
        w.writerows(settlements)

    with (out_dir / "fee_plans.json").open("w", encoding="utf-8") as f:
        json.dump(FEE_PLANS, f, indent=2)

    print(f"Generated {total} records → {out_dir}/")
    print(f"  Clean:    44  |  E01: 10  |  E04: 3  |  E03: 2  |  E06: 2  |  E05: 1")
    print(f"  Expected exceptions after classify: 18")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Ledgerscope batch")
    parser.add_argument("--seed",    type=int,  default=42,           help="RNG seed")
    parser.add_argument("--out-dir", type=str,  default="synthetic",  help="Output directory")
    args = parser.parse_args()
    generate(seed=args.seed, out_dir=args.out_dir)
