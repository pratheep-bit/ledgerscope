"""
ingest.py — Load and join transaction/settlement data.

All monetary values converted to integer paise on load. Fails loud on malformed
input — this is a finance tool, silent None is not acceptable for required fields.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from .models import Transaction, Settlement, FeePlan


def _parse_bool(val: str) -> bool:
    """Parse boolean CSV values. Accepts 'true'/'false' (case-insensitive)."""
    v = val.strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no", ""):
        return False
    raise ValueError(f"Cannot parse bool from: {val!r}")


def _require(row: dict, field: str, filename: str) -> str:
    """Return the field value, raising clearly if it's absent or empty."""
    val = row.get(field)
    if val is None:
        raise ValueError(f"Required field {field!r} missing from row in {filename}: {row}")
    return val


def load_transactions(path: str | Path) -> list[Transaction]:
    """Read transactions CSV, returning a list of Transaction objects."""
    path = Path(path)
    results = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # row 1 is header
            try:
                results.append(Transaction(
                    txn_id=_require(row, "txn_id", str(path)),
                    merchant_id=_require(row, "merchant_id", str(path)),
                    fee_plan_id=_require(row, "fee_plan_id", str(path)),
                    amount_paise=int(_require(row, "amount_paise", str(path))),
                    currency=_require(row, "currency", str(path)),
                    payment_method=_require(row, "payment_method", str(path)),
                    card_network=row.get("card_network") or None,
                    is_international=_parse_bool(_require(row, "is_international", str(path))),
                    captured_at=_require(row, "captured_at", str(path)),
                    is_refund=_parse_bool(_require(row, "is_refund", str(path))),
                    parent_txn_id=row.get("parent_txn_id") or None,
                    is_credit_on_upi=_parse_bool(row.get("is_credit_on_upi", "false")),
                ))
            except (ValueError, KeyError) as e:
                raise ValueError(f"Error parsing transaction row {i} in {path}: {e}") from e
    return results


def load_settlements(path: str | Path) -> list[Settlement]:
    """Read settlements CSV, returning a list of Settlement objects.

    tax_paise: empty string → None (not 0) — this distinction feeds E05.
    """
    path = Path(path)
    results = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            try:
                raw_tax = row.get("tax_paise", "").strip()
                tax_paise = int(raw_tax) if raw_tax != "" else None

                results.append(Settlement(
                    settlement_id=_require(row, "settlement_id", str(path)),
                    txn_id=_require(row, "txn_id", str(path)),
                    settlement_batch=_require(row, "settlement_batch", str(path)),
                    settled_at=_require(row, "settled_at", str(path)),
                    gross_paise=int(_require(row, "gross_paise", str(path))),
                    fee_paise=int(_require(row, "fee_paise", str(path))),
                    tax_paise=tax_paise,
                    net_paise=int(_require(row, "net_paise", str(path))),
                ))
            except (ValueError, KeyError) as e:
                raise ValueError(f"Error parsing settlement row {i} in {path}: {e}") from e
    return results


def load_fee_plans(path: str | Path) -> dict[str, FeePlan]:
    """Read fee_plans.json, returning a dict keyed by fee_plan_id."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    plans = {}
    for entry in raw:
        plan_id = entry.get("fee_plan_id")
        if not plan_id:
            raise ValueError(f"fee_plan entry missing 'fee_plan_id': {entry}")
        plans[plan_id] = FeePlan(
            fee_plan_id=plan_id,
            default_rate_bps=int(entry["default_rate_bps"]),
            overrides=entry.get("overrides", {}),
        )
    return plans


def join(
    transactions: list[Transaction],
    settlements: list[Settlement],
) -> tuple[list[tuple[Transaction, Settlement]], list[Transaction], list[Settlement]]:
    """Inner-join transactions and settlements on txn_id.

    Returns:
        - joined: list of (Transaction, Settlement) pairs
        - txn_orphans: transactions with no matching settlement
        - stl_orphans: settlements with no matching transaction

    Orphans are NOT silently dropped — they are returned so run.py can report them.
    """
    stl_by_txn: dict[str, Settlement] = {}
    stl_orphan_ids: set[str] = set()

    for s in settlements:
        if s.txn_id in stl_by_txn:
            # Duplicate settlement for same txn_id — both become orphans
            stl_orphan_ids.add(s.txn_id)
        stl_by_txn[s.txn_id] = s

    joined = []
    txn_orphans = []
    claimed_txn_ids: set[str] = set()

    for t in transactions:
        if t.txn_id in stl_by_txn and t.txn_id not in stl_orphan_ids:
            joined.append((t, stl_by_txn[t.txn_id]))
            claimed_txn_ids.add(t.txn_id)
        else:
            txn_orphans.append(t)

    stl_orphans = [s for s in settlements if s.txn_id not in claimed_txn_ids]

    return joined, txn_orphans, stl_orphans
