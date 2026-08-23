# Ledgerscope — Build Progress

Last updated: 2026-08-23T09:02:00+05:30

## Status summary
Current step: COMPLETE (All Steps 1–14 Done & Re-verified)
Blocking issues: none

## Step checklist
- [x] Step 1 — Repo scaffold
- [x] Step 2 — models.py
- [x] Step 3 — rates.py
- [x] Step 4 — ingest.py
- [x] Step 5 — engine.py + test_engine.py (CRITICAL: TEST 1 + rounding table)
- [x] Step 6 — generate.py (62-record synthetic batch)
- [x] Step 7 — classify.py + test_classify.py
- [x] Step 8 — rootcause.py + test_rootcause.py (CRITICAL: TEST 2, 3, 4, heterogeneous regression test)
- [x] Step 9 — narrate.py + test_narrate.py (CRITICAL: figure-guard test)
- [x] Step 10 — report.py
- [x] Step 11 — run.py (CLI wiring + AnthropicNarrationClient wrapper)
- [x] Step 12 — full end-to-end run, commit sample output
- [x] Step 13 — README finalization
- [x] Step 14 — re-verify RATE BASIS and market-fact claims (within 24h of submission)

## Step 14 Re-Verification Log (2026-08-22)

1. **Pricing Page (`https://razorpay.com/pricing/`)**:
   - Platform fee: "Razorpay charges 2% + GST per transaction" across cards, UPI, wallets, net banking.
   - Zero MDR on standard bank-to-bank UPI & RuPay Debit Card.
   - RuPay Credit Card on UPI: 2.15% + GST platform fee.
   - GST rate: 18% applicable on platform fees.
   - Result: **PASS** (Confirmed verbatim on live site).

2. **Agentic Banking Page (`https://razorpay.com/agentic-business-banking/`)**:
   - Active agents: Insights, Receivables, Payout, Bookkeeping, Reporting.
   - Tax Payments: Handled separately via RazorpayX Tax Payments (TDS & Advance Tax only; settlement fee reconciliation & GST-on-MDR input tax credit remain an open gap).
   - Result: **PASS** (Confirmed market positioning gap).

## Test results log

### Full test suite (26 tests)
Command: `.venv/bin/pytest -v`
Result: PASS
Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
collected 26 items

tests/test_classify.py::test_classify_e01_fee_rate_mismatch PASSED       [  3%]
tests/test_classify.py::test_classify_e03_gst_base_mismatch PASSED       [  7%]
tests/test_classify.py::test_classify_e04_rounding_drift PASSED          [ 11%]
tests/test_classify.py::test_classify_e05_missing_tax_line PASSED        [ 15%]
tests/test_classify.py::test_classify_e06_refund_fee_not_reversed PASSED [ 19%]
tests/test_classify.py::test_classify_e09_unexplained PASSED             [ 23%]
tests/test_engine.py::test_test1_rounding_half_up PASSED                 [ 26%]
tests/test_engine.py::test_rounding_boundary_lands_on_dot5 PASSED        [ 30%]
tests/test_engine.py::test_rounding_boundary_just_below_dot5 PASSED      [ 34%]
tests/test_engine.py::test_rounding_boundary_just_above_dot5 PASSED      [ 38%]
tests/test_engine.py::test_rounding_boundary_truncation_produces_exception PASSED [ 42%]
tests/test_engine.py::test_international_rate_applied PASSED             [ 46%]
tests/test_engine.py::test_negotiated_rate_override PASSED               [ 50%]
tests/test_narrate.py::test_narrate_template_fallback_when_no_client PASSED [ 53%]
tests/test_narrate.py::test_narrate_template_content_likely_root_cause PASSED [ 57%]
tests/test_narrate.py::test_narrate_template_content_possible_pattern PASSED [ 61%]
tests/test_narrate.py::test_narrate_falls_back_on_hallucination PASSED   [ 65%]
tests/test_narrate.py::test_narrate_good_client_passes_through PASSED    [ 69%]
tests/test_rootcause.py::test_test2_systemic_cluster_promoted PASSED     [ 73%]
tests/test_rootcause.py::test_test3_weak_pattern_not_promoted PASSED     [ 76%]
tests/test_rootcause.py::test_test4_outliers_do_not_hijack PASSED        [ 80%]
tests/test_rootcause.py::test_no_duplicate_member_sets PASSED            [ 84%]
tests/test_rootcause.py::test_finding_count_is_reasonable PASSED         [ 88%]
tests/test_rootcause.py::test_heterogeneous_default_plan_does_not_merge_distinct_causes PASSED [ 92%]
tests/test_rootcause.py::test_empty_exceptions_returns_empty PASSED      [ 96%]
tests/test_rootcause.py::test_single_exception_below_min_support PASSED  [100%]

============================== 26 passed in 0.08s ==============================
```

### End-to-end run
Command: `python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm`
Output:
```
[1/5] Loading data from synthetic/
      62 transactions, 62 settlements
      Joined: 62  |  Txn orphans: 0  |  Stl orphans: 0
[2/5] Running engine on 62 joined pairs …
[3/5] Classifying exceptions …
      Matched: 44  |  Exceptions: 18  |  Orphans: 0
[4/5] Root-cause analysis on 18 exceptions (batch span: 3 days) …
      Found 4 finding(s)
[5/5] Narrating findings (client=template) …

Done. Reports written to reports/
  report.json  — machine-readable full report
  report.md    — human-readable summary
  audit.jsonl  — per-record decision log
```

## Demo & Narration Mode Selection
- **Default / Pitch mode**: Deterministic template narration (`--no-llm`) is the primary recommendation for live judging review because it requires zero external API key dependencies, executes in milliseconds, and is 100% deterministic and provably immune to hallucinated figures.
- **LLM mode**: When `ANTHROPIC_API_KEY` is provided, `AnthropicNarrationClient` (`claude-sonnet-4-6`) activates seamlessly, protected by runtime token-level numeric verification in `_assert_no_invented_figures()`.

## Known deviations from spec
- `Transaction` dataclass has an extra field `is_credit_on_upi: bool = False` (with default) to support the verified RuPay-UPI-credit rate override (2.15% MDR) in `rates.py::applicable_rate_bps`.
- Deduplication in `rootcause.py`: Candidates with identical transaction ID sets are collapsed into a single finding with merged shared attributes, and zero-variance attributes across the batch are pruned before candidate generation.
- Subsumption in `rootcause.py`: Findings with `exception_code` in their shared attributes are protected from being subsumed by broader configuration attributes (e.g. default `fee_plan_id=PLN_STD`).
- Batch span computation in `run.py`: Computed as distinct calendar dates in `settled_at` (3 days across Aug 14, 15, 16) resulting in scaling factor x10.0 to a 30-day month.

## Definition of done check
- [x] All steps 1–14 checked off and fully verified
- [x] `pytest -v` passes completely — 26 passed in 0.08s
- [x] TEST 3 (the negative test) passes — re-confirmed
- [x] `test_heterogeneous_default_plan_does_not_merge_distinct_causes` passes
- [x] `python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm` produces clean findings/confidences/impacts (4 findings, zero conflation)
- [x] `synthetic/` and `reports/` contain real generated output
- [x] `RATE BASIS` block appears in both `rates.py` and the README, word for word
- [x] `FAILURES.md` has real, specific entries with complete failure-recovery narratives
- [x] README shows real numbers from actual run (not illustrative)
- [x] Step 14 re-verification completed with PASS status on both market facts
