# Ledgerscope — Build Progress

Last updated: 2026-08-22T11:38:00+05:30

## Status summary
Current step: 14 (COMPLETE — pending 24h rate re-verification)
Blocking issues: none

## Step checklist
- [x] Step 1 — Repo scaffold
- [x] Step 2 — models.py
- [x] Step 3 — rates.py
- [x] Step 4 — ingest.py
- [x] Step 5 — engine.py + test_engine.py (CRITICAL: TEST 1 + rounding table)
- [x] Step 6 — generate.py (62-record synthetic batch)
- [x] Step 7 — classify.py + test_classify.py
- [x] Step 8 — rootcause.py + test_rootcause.py (CRITICAL: TEST 2, 3, 4, 5)
- [x] Step 9 — narrate.py + test_narrate.py (CRITICAL: figure-guard test)
- [x] Step 10 — report.py
- [x] Step 11 — run.py (CLI wiring)
- [x] Step 12 — full end-to-end run, commit sample output
- [x] Step 13 — README finalization
- [ ] Step 14 — re-verify RATE BASIS and market-fact claims (must do within 24h of submission)

## Test results log

### Full test suite (24 tests)
Command: `.venv/bin/pytest -v`
Result: PASS
Output:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
collected 24 items

tests/test_classify.py::test_classify_e01_fee_rate_mismatch PASSED       [  4%]
tests/test_classify.py::test_classify_e03_gst_base_mismatch PASSED       [  8%]
tests/test_classify.py::test_classify_e04_rounding_drift PASSED          [ 12%]
tests/test_classify.py::test_classify_e05_missing_tax_line PASSED        [ 16%]
tests/test_classify.py::test_classify_e06_refund_fee_not_reversed PASSED [ 20%]
tests/test_classify.py::test_classify_e09_unexplained PASSED             [ 25%]
tests/test_engine.py::test_test1_rounding_half_up PASSED                 [ 29%]
tests/test_engine.py::test_rounding_boundary_lands_on_dot5 PASSED        [ 33%]
tests/test_engine.py::test_rounding_boundary_just_below_dot5 PASSED      [ 37%]
tests/test_engine.py::test_rounding_boundary_just_above_dot5 PASSED      [ 41%]
tests/test_engine.py::test_rounding_boundary_truncation_produces_exception PASSED [ 45%]
tests/test_engine.py::test_international_rate_applied PASSED             [ 50%]
tests/test_engine.py::test_negotiated_rate_override PASSED               [ 54%]
tests/test_narrate.py::test_narrate_template_fallback_when_no_client PASSED [ 58%]
tests/test_narrate.py::test_narrate_template_content_likely_root_cause PASSED [ 62%]
tests/test_narrate.py::test_narrate_template_content_possible_pattern PASSED [ 66%]
tests/test_narrate.py::test_narrate_falls_back_on_hallucination PASSED   [ 70%]
tests/test_narrate.py::test_narrate_good_client_passes_through PASSED    [ 75%]
tests/test_rootcause.py::test_test2_systemic_cluster_promoted PASSED     [ 79%]
tests/test_rootcause.py::test_test3_weak_pattern_not_promoted PASSED     [ 83%]
tests/test_rootcause.py::test_test4_outliers_do_not_hijack PASSED        [ 87%]
tests/test_rootcause.py::test_test5_deduplication_no_identical_member_sets PASSED [ 91%]
tests/test_rootcause.py::test_empty_exceptions_returns_empty PASSED      [ 95%]
tests/test_rootcause.py::test_single_exception_below_min_support PASSED  [100%]

============================== 24 passed in 0.06s ==============================
```

### End-to-end run
```
python -m ledgerscope.generate --seed 42
python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm

[1/5] Loading data from synthetic/
      62 transactions, 62 settlements
      Joined: 62  |  Txn orphans: 0  |  Stl orphans: 0
[2/5] Running engine on 62 joined pairs …
[3/5] Classifying exceptions …
      Matched: 44  |  Exceptions: 18  |  Orphans: 0
[4/5] Root-cause analysis on 18 exceptions (batch span: 3 days) …
      Found 11 finding(s)
[5/5] Narrating findings (client=template) …

Done. Reports written to reports/
  report.json  — machine-readable full report
  report.md    — human-readable summary
  audit.jsonl  — per-record decision log
```

## Open questions
- Which LLM API/key to wire up for the real (non-template) narrate path? Left as client=None (--no-llm always-on) until specified.

## Known deviations from spec
- `Transaction` dataclass has an extra field `is_credit_on_upi: bool = False` (with default) not listed in Step 2's schema. Added deliberately to support the RuPay-UPI-credit rate override in `rates.py::applicable_rate_bps`.
- Deduplication in `rootcause.py`: Candidates with identical transaction ID sets are collapsed into a single finding with merged shared attributes, and zero-variance attributes across the batch are pruned before candidate generation.
- Batch span computation in `run.py`: Computed as distinct calendar dates in `settled_at` (3 days across Aug 14, 15, 16) resulting in scaling factor x10.0 to a 30-day month.

## Definition of done check
- [x] All steps 1–13 checked off (Step 14 pending 24h re-verification)
- [x] `pytest -v` passes completely — 24 passed in 0.06s
- [x] TEST 3 (the negative test) passes — re-confirmed
- [x] TEST 5 (deduplication check) passes — no identical member sets
- [x] `python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm` produces findings/confidences/impacts
- [x] `synthetic/` and `reports/` contain real generated output
- [x] `RATE BASIS` block appears in both `rates.py` and the README, word for word
- [x] `FAILURES.md` has real, specific entries
- [x] README shows real numbers from actual run (not illustrative)
- [ ] Step 14 re-verification within 24h of submission
