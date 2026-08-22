# LEDGERSCOPE — batch STL_2026_08 · 62 records

  Matched       44 / 62      (71.0%)
  Exceptions    18 / 62      (29.0%)
  Unexplained    0 / 18      (E09 residual)

## EXCEPTIONS BY CATEGORY
  E01  FEE_RATE_MISMATCH               10
  E03  GST_BASE_MISMATCH               2
  E04  ROUNDING_DRIFT                  3
  E05  MISSING_TAX_LINE                1
  E06  REFUND_FEE_NOT_REVERSED         2

────────────────────────────────────────────────────────────────
RC_001   ● LIKELY ROOT CAUSE     confidence: HIGH
────────────────────────────────────────────────────────────────
Cause          RATE_MISCONFIGURATION
Shared         fee_plan_id=PLN_ENT_2024  ·  exception_code=E01  ·  payment_method=netbanking  ·  card_network=None  ·  is_international=False  ·  is_refund=False  ·  settlement_batch=STL_2026_08
Support        10 exceptions (56% of all exceptions in batch)
Deviation      positive mean 5.268% · CV 0.006 · direction consistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹33.32   (computed from these 10 records)
Projected monthly impact   ₹333.20  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Audit the netbanking rate on fee plan PLN_ENT_2024 — settlement is applying a rate inconsistent with the plan's configured rate.

Narration (template): 10 exceptions sharing {'fee_plan_id': 'PLN_ENT_2024', 'exception_code': 'E01', 'payment_method': 'netbanking', 'card_network': None, 'is_international': False, 'is_refund': False, 'settlement_batch': 'STL_2026_08'} show a consistent positive deviation (confidence: high). Observed batch impact: 3332 paise. Audit the netbanking rate on fee plan PLN_ENT_2024 — settlement is applying a rate inconsistent with the plan's configured rate.

────────────────────────────────────────────────────────────────
RC_002   ○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE     confidence: LOW
────────────────────────────────────────────────────────────────
Shared         fee_plan_id=PLN_STD  ·  is_international=False  ·  settlement_batch=STL_2026_08
Support        8 exceptions (44% of all exceptions in batch)
Deviation      negative mean 184.946% · CV 1.709 · direction inconsistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹354.63   (computed from these 8 records)
Projected monthly impact   ₹3,546.30  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Check the rounding mode used in the settlement system — expected half-up (Indian financial standard), but truncation appears to be applied on plan PLN_STD.

Narration (template): 8 exceptions share {'fee_plan_id': 'PLN_STD', 'is_international': False, 'settlement_batch': 'STL_2026_08'}, covering 44% of exceptions in this batch — below the threshold to confirm a cause. Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Check the rounding mode used in the settlement system — expected half-up (Indian financial standard), but truncation appears to be applied on plan PLN_STD.

