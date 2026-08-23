# Ledgerscope — Statistical Validation Report

**Date**: 2026-08-23
**Test Suite**: `test_statistical_validation.py`

## Summary Metrics

| Metric | Sample Size | Measured Value | Standard / Target | Verdict |
|--------|-------------|----------------|-------------------|---------|
| **False Positive Rate** | 100 batches (1,500–4,000 txns) | **0.0%** (0/100) | 0.0% false promotions | **PASS** |
| **Recall Rate** | 100 batches (2,000–5,000 txns) | **100.0%** (100/100) | ≥ 95.0% recall | **PASS** |

---

## Part A: False Positive Validation (Unrelated Random Noise)

- **Goal**: Verify that when exceptions are completely random and uncorrelated (mixed payment methods, random card networks, random fee plans, random timestamps, mixed positive/negative deviation directions), `detect()` NEVER manufactures a false `likely_root_cause` promotion.
- **Measured FPR**: `0.0%` (0 / 100 batches falsely promoted).

### Example Passing Cases (No False Positives):
- **Batch `CLEAN_BATCH_000`** (35 exceptions): Produced `51` findings, 0 promoted to `likely_root_cause`. All remained classified as `possible_pattern — insufficient evidence` or suppressed below support threshold.
- **Batch `CLEAN_BATCH_001`** (24 exceptions): Produced `29` findings, 0 promoted to `likely_root_cause`. All remained classified as `possible_pattern — insufficient evidence` or suppressed below support threshold.
- **Batch `CLEAN_BATCH_002`** (38 exceptions): Produced `62` findings, 0 promoted to `likely_root_cause`. All remained classified as `possible_pattern — insufficient evidence` or suppressed below support threshold.

> **Result**: Zero false positives across 100 independent random noise batches.

---

## Part B: Recall Validation (Injected Ground-Truth Root Causes)

- **Goal**: Verify that when a genuine systemic discrepancy is present (>50% coverage, consistent sign, low variance across shared attributes), `detect()` reliably promotes it to `likely_root_cause`.
- **Measured Recall**: `100.0%` (100 / 100 injected causes detected).

### Example Passing Recall Detections:
- **Batch `INJ_BATCH_000`** (40 exceptions, 23 injected = 57.5% coverage):
  - Injected: `method=netbanking`, `plan=PLN_ENT_2024`, `code=E02`
  - Detected: Verdict=`likely_root_cause`, Confidence=`high`, Shared Attrs={'payment_method': 'netbanking', 'fee_plan_id': 'PLN_ENT_2024', 'exception_code': 'E02', 'card_network': None, 'is_international': False, 'is_refund': False, 'settlement_batch': 'STL_02'}
- **Batch `INJ_BATCH_001`** (26 exceptions, 18 injected = 69.2% coverage):
  - Injected: `method=wallet`, `plan=PLN_ENT_2024`, `code=E04`
  - Detected: Verdict=`likely_root_cause`, Confidence=`high`, Shared Attrs={'payment_method': 'wallet', 'fee_plan_id': 'PLN_ENT_2024', 'exception_code': 'E04', 'card_network': None, 'is_international': False, 'is_refund': False, 'settlement_batch': 'STL_04'}
- **Batch `INJ_BATCH_002`** (37 exceptions, 22 injected = 59.5% coverage):
  - Injected: `method=netbanking`, `plan=PLN_ENT_2024`, `code=E03`
  - Detected: Verdict=`likely_root_cause`, Confidence=`high`, Shared Attrs={'payment_method': 'netbanking', 'fee_plan_id': 'PLN_ENT_2024', 'exception_code': 'E03', 'card_network': None, 'is_international': False, 'is_refund': False, 'settlement_batch': 'STL_01'}

> **Result**: 100% recall across 100 injected systemic anomaly batches.
