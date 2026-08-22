"""
report.py — Generate three output files from already-computed results.

This module performs NO calculation — it only formats and writes. All numbers
come from MatchResult objects and Finding dicts already produced upstream.

Outputs:
  report.json  — machine-readable full report
  report.md    — human-readable formatted report
  audit.jsonl  — one JSON line per MatchResult (full per-record decision log)
"""
from __future__ import annotations
import dataclasses
import json
from pathlib import Path
from datetime import datetime, timezone


def write_report(
    batch_id: str,
    results: list,           # list[MatchResult]
    findings: list[dict],    # list[Finding dict]
    out_dir: str | Path,
) -> None:
    """Write all three output files to out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(batch_id, results, findings, out_dir / "report.json")
    _write_markdown(batch_id, results, findings, out_dir / "report.md")
    _write_jsonl(results, out_dir / "audit.jsonl")


# ---------------------------------------------------------------------------
# report.json
# ---------------------------------------------------------------------------

def _write_json(batch_id, results, findings, path):
    total = len(results)
    matched = sum(1 for r in results if r.status == "MATCHED")
    exceptions = sum(1 for r in results if r.status == "EXCEPTION")
    orphans = sum(1 for r in results if r.status == "ORPHAN")

    match_rate = round(matched / total, 4) if total else 0.0

    report = {
        "batch_id": batch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_records": total,
            "matched": matched,
            "exceptions": exceptions,
            "orphans": orphans,
            "match_rate": match_rate,
        },
        "results": [dataclasses.asdict(r) for r in results],
        "findings": findings,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


# ---------------------------------------------------------------------------
# report.md
# ---------------------------------------------------------------------------

def _write_markdown(batch_id, results, findings, path):
    total = len(results)
    matched = sum(1 for r in results if r.status == "MATCHED")
    exceptions_list = [r for r in results if r.status == "EXCEPTION"]
    n_exc = len(exceptions_list)
    n_unexplained = sum(1 for r in exceptions_list if r.exception_code == "E09")

    lines = []
    lines.append(f"# LEDGERSCOPE — batch {batch_id} · {total} records")
    lines.append("")
    lines.append(f"  Matched      {matched:3d} / {total}      ({matched/total*100:.1f}%)")
    lines.append(f"  Exceptions   {n_exc:3d} / {total}      ({n_exc/total*100:.1f}%)")
    lines.append(f"  Unexplained  {n_unexplained:3d} / {n_exc}      (E09 residual)")
    lines.append("")

    # Exceptions by category
    from collections import Counter
    exc_counts = Counter(r.exception_code for r in exceptions_list if r.exception_code)
    exc_names = {
        "E01": "FEE_RATE_MISMATCH",
        "E02": "GST_RATE_MISMATCH",
        "E03": "GST_BASE_MISMATCH",
        "E04": "ROUNDING_DRIFT",
        "E05": "MISSING_TAX_LINE",
        "E06": "REFUND_FEE_NOT_REVERSED",
        "E07": "SETTLEMENT_TIMING",
        "E08": "DUPLICATE_DEDUCTION",
        "E09": "UNEXPLAINED",
    }

    lines.append("## EXCEPTIONS BY CATEGORY")
    for code in sorted(exc_counts.keys()):
        name = exc_names.get(code, code)
        lines.append(f"  {code}  {name:<30s}  {exc_counts[code]}")
    lines.append("")

    # Findings
    if not findings:
        lines.append("*No patterns detected.*")
    else:
        for i, f in enumerate(findings, start=1):
            rc_id = f"RC_{i:03d}"
            is_likely = f["verdict"] == "likely_root_cause"
            marker = "● LIKELY ROOT CAUSE" if is_likely else "○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE"
            conf = f["confidence"].upper()

            lines.append("─" * 64)
            lines.append(f"{rc_id}   {marker}{'':>5}confidence: {conf}")
            lines.append("─" * 64)

            if is_likely:
                lines.append(f"Cause          {f['cause_type']}")
            attr_str = "  ·  ".join(f"{k}={v}" for k, v in f["shared_attributes"].items())
            lines.append(f"Shared         {attr_str}")
            pct = f"{f['coverage_ratio']*100:.0f}%"
            lines.append(f"Support        {f['support_count']} exceptions ({pct} of all exceptions in batch)")
            dev = f["deviation_summary"]
            lines.append(f"Deviation      {dev['sign']} mean {dev['mean_deviation_ratio']*100:.3f}%"
                         f" · CV {dev['coefficient_of_variation']:.3f}"
                         f" · direction {'consistent' if dev['consistent'] else 'inconsistent'}")
            lines.append(f"Rule           {f['rule_id']}")
            lines.append("")

            obs_paise = f["observed_batch_impact_paise"]
            proj = f["projected_monthly_impact"]
            obs_rupees = obs_paise / 100
            proj_rupees = proj["value_paise"] / 100
            lines.append(f"Observed batch impact      ₹{obs_rupees:,.2f}   (computed from these {f['support_count']} records)")
            lines.append(f"Projected monthly impact   ₹{proj_rupees:,.2f}  ← {proj['basis']}")
            lines.append("")
            lines.append(f"→ ACTION  {f['controller_action']}")

            if f.get("narration"):
                lines.append("")
                lines.append(f"Narration ({f.get('narration_source', 'template')}): {f['narration']}")

            lines.append("")

    with path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# audit.jsonl
# ---------------------------------------------------------------------------

def _write_jsonl(results, path):
    with path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(dataclasses.asdict(r)) + "\n")
