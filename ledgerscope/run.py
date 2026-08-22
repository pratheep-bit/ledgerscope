"""
run.py — CLI orchestration for Ledgerscope.

Wires together: ingest → engine.recompute → classify → rootcause.detect →
narrate → report. No new logic here — only sequencing and I/O.

Usage:
    python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm

Flags:
    --batch   Input directory containing transactions.csv, settlements.csv,
              fee_plans.json
    --out     Output directory for report.json, report.md, audit.jsonl
    --no-llm  Force client=None in narrate (template fallback, always safe)
    --seed    Not used by run.py itself (passed to generate.py only). Included
              here for discoverability but has no effect.
"""
from __future__ import annotations
import argparse
import dataclasses
import sys
from pathlib import Path

from .ingest import load_transactions, load_settlements, load_fee_plans, join
from .engine import recompute
from .classify import classify
from .rootcause import detect
from .narrate import narrate
from .report import write_report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ledgerscope — deterministic settlement fee reconciliation"
    )
    parser.add_argument(
        "--batch", required=True,
        help="Input directory with transactions.csv, settlements.csv, fee_plans.json"
    )
    parser.add_argument(
        "--out", required=True,
        help="Output directory for report.json, report.md, audit.jsonl"
    )
    parser.add_argument(
        "--no-llm", action="store_true", default=False,
        help="Force client=None in narrate (deterministic template always used)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Passthrough to generate.py only; has no effect on run.py"
    )
    args = parser.parse_args(argv)

    batch_dir = Path(args.batch)
    out_dir = Path(args.out)

    # ------------------------------------------------------------------
    # 1. Ingest
    # ------------------------------------------------------------------
    print(f"[1/5] Loading data from {batch_dir}/")
    transactions = load_transactions(batch_dir / "transactions.csv")
    settlements  = load_settlements(batch_dir / "settlements.csv")
    fee_plans    = load_fee_plans(batch_dir / "fee_plans.json")

    joined, txn_orphans, stl_orphans = join(transactions, settlements)

    print(f"      {len(transactions)} transactions, {len(settlements)} settlements")
    print(f"      Joined: {len(joined)}  |  Txn orphans: {len(txn_orphans)}  |  Stl orphans: {len(stl_orphans)}")

    # ------------------------------------------------------------------
    # 2. Engine — recompute expected fee/tax per joined pair
    # ------------------------------------------------------------------
    print(f"[2/5] Running engine on {len(joined)} joined pairs …")
    results = []
    for txn, stl in joined:
        plan = fee_plans.get(txn.fee_plan_id)
        if plan is None:
            print(f"      WARNING: no fee plan found for {txn.fee_plan_id!r} "
                  f"(txn {txn.txn_id}) — skipping", file=sys.stderr)
            continue
        mr = recompute(txn, stl, plan)
        results.append((mr, txn, stl))

    # Add orphans as ORPHAN status records
    for txn in txn_orphans:
        plan = fee_plans.get(txn.fee_plan_id)
        default_rate = plan.default_rate_bps if plan else 200
        orphan_mr = _make_orphan_mr(txn, default_rate)
        results.append((orphan_mr, txn, None))

    # ------------------------------------------------------------------
    # 3. Classify — assign exception codes
    # ------------------------------------------------------------------
    print(f"[3/5] Classifying exceptions …")
    classified = []
    exceptions = []
    for mr, txn, stl in results:
        if mr.status == "ORPHAN" or stl is None:
            classified.append(mr)
            continue
        # Run classify on:
        #   (a) records the engine already flagged as EXCEPTION (non-zero delta)
        #   (b) refund transactions even if delta=0 — E06 fires when is_refund=True
        #       and fee_delta >= 0, regardless of whether total_delta is zero.
        needs_classify = (mr.status == "EXCEPTION") or txn.is_refund
        if needs_classify:
            code, rule = classify(mr, txn, stl)
            mr = dataclasses.replace(mr, exception_code=code, rule_fired=rule)
            # Reclassify as EXCEPTION if a rule fired on a previously-MATCHED record
            if mr.status == "MATCHED" and code not in (None, "E09"):
                mr = dataclasses.replace(mr, status="EXCEPTION")
            if mr.status == "EXCEPTION":
                exceptions.append(mr)
        classified.append(mr)

    n_matched   = sum(1 for r in classified if r.status == "MATCHED")
    n_exception = sum(1 for r in classified if r.status == "EXCEPTION")
    n_orphan    = sum(1 for r in classified if r.status == "ORPHAN")
    print(f"      Matched: {n_matched}  |  Exceptions: {n_exception}  |  Orphans: {n_orphan}")

    # ------------------------------------------------------------------
    # 4. Root cause — detect patterns across exceptions
    # ------------------------------------------------------------------
    # Determine batch span in days from settled_at timestamps
    batch_span_days = _compute_batch_span(joined)
    print(f"[4/5] Root-cause analysis on {len(exceptions)} exceptions "
          f"(batch span: {batch_span_days} days) …")

    # rootcause.detect reads CANDIDATE_ATTRS from the exception objects:
    # ["payment_method", "card_network", "fee_plan_id", "is_international",
    #  "is_refund", "settlement_batch", "exception_code"]
    # MatchResult only has exception_code + deviation_ratio + total_delta_paise.
    # We need to attach the transaction/settlement attributes too.
    exc_for_rootcause = _build_exc_for_rootcause(exceptions, results)

    findings = detect(exc_for_rootcause, batch_span_days=batch_span_days)
    print(f"      Found {len(findings)} finding(s)")

    # ------------------------------------------------------------------
    # 5. Narrate and attach to findings
    # ------------------------------------------------------------------
    client = _get_narration_client(args.no_llm)
    print(f"[5/5] Narrating findings (client={'llm' if client else 'template'}) …")

    enriched_findings = []
    for i, f in enumerate(findings):
        text, source = narrate(f, client=client)
        enriched = dict(f)
        enriched["finding_id"] = f"RC_{i+1:03d}"
        enriched["narration"] = text
        enriched["narration_source"] = source
        enriched_findings.append(enriched)

    # ------------------------------------------------------------------
    # Write report
    # ------------------------------------------------------------------
    batch_id = _infer_batch_id(settlements)
    write_report(batch_id, classified, enriched_findings, out_dir)

    print(f"\nDone. Reports written to {out_dir}/")
    print(f"  report.json  — machine-readable full report")
    print(f"  report.md    — human-readable summary")
    print(f"  audit.jsonl  — per-record decision log")


def _make_orphan_mr(txn, default_rate_bps: int):
    """Create a minimal MatchResult for a transaction with no matching settlement."""
    from .models import MatchResult
    return MatchResult(
        txn_id=txn.txn_id,
        status="ORPHAN",
        expected_fee_paise=0,
        actual_fee_paise=0,
        fee_delta_paise=0,
        expected_tax_paise=0,
        actual_tax_paise=None,
        tax_delta_paise=0,
        total_delta_paise=0,
        deviation_ratio=0.0,
        exception_code=None,
        rule_fired=None,
        applied_rate_bps=default_rate_bps,
        implied_rate_bps=None,
    )


def _build_exc_for_rootcause(exceptions, all_results):
    """Build enriched exception objects for rootcause.detect.

    rootcause.detect reads CANDIDATE_ATTRS:
      ["payment_method", "card_network", "fee_plan_id", "is_international",
       "is_refund", "settlement_batch", "exception_code"]
    plus deviation_ratio and total_delta_paise from MatchResult.

    MatchResult only carries exception_code + deviation_ratio + total_delta_paise.
    We need transaction+settlement attributes too. Build a simple namespace object
    that has all of these fields.
    """
    # Build a lookup from txn_id to (txn, stl)
    txn_stl_map = {}
    for mr, txn, stl in all_results:
        txn_stl_map[mr.txn_id] = (txn, stl)

    class _ExcProxy:
        """Simple proxy combining MatchResult fields with Transaction/Settlement fields."""
        __slots__ = [
            "txn_id", "payment_method", "card_network", "fee_plan_id",
            "is_international", "is_refund", "settlement_batch",
            "exception_code", "deviation_ratio", "total_delta_paise",
        ]
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    enriched = []
    for mr in exceptions:
        txn, stl = txn_stl_map.get(mr.txn_id, (None, None))
        enriched.append(_ExcProxy(
            txn_id=mr.txn_id,
            payment_method=txn.payment_method if txn else None,
            card_network=txn.card_network if txn else None,
            fee_plan_id=txn.fee_plan_id if txn else None,
            is_international=txn.is_international if txn else False,
            is_refund=txn.is_refund if txn else False,
            settlement_batch=stl.settlement_batch if stl else None,
            exception_code=mr.exception_code,
            deviation_ratio=mr.deviation_ratio,
            total_delta_paise=mr.total_delta_paise,
        ))
    return enriched


def _compute_batch_span(joined: list) -> int:
    """Compute the batch span in days from distinct calendar dates in settled_at."""
    from datetime import datetime
    dates = set()
    for _, stl in joined:
        try:
            dt = datetime.fromisoformat(stl.settled_at.replace("Z", "+00:00"))
            dates.add(dt.date())
        except (ValueError, AttributeError):
            pass
    return max(len(dates), 1)


def _infer_batch_id(settlements: list) -> str:
    """Use the settlement_batch value from the first settlement, or a default."""
    if settlements:
        return settlements[0].settlement_batch
    return "UNKNOWN_BATCH"


def _get_narration_client(no_llm: bool):
    """Obtain narration client. If no_llm is set or Anthropic client cannot be
    constructed (missing dependency or ANTHROPIC_API_KEY), returns None so narrate
    falls back cleanly to the deterministic template.
    """
    if no_llm:
        return None
    try:
        from .llm_client import AnthropicNarrationClient
        return AnthropicNarrationClient()
    except Exception:
        return None


if __name__ == "__main__":
    main()
