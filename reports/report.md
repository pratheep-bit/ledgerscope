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
RC_002   ○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE     confidence: MEDIUM
────────────────────────────────────────────────────────────────
Shared         exception_code=E04  ·  payment_method=netbanking  ·  fee_plan_id=PLN_STD  ·  card_network=None  ·  is_international=False  ·  is_refund=False  ·  settlement_batch=STL_2026_08
Support        3 exceptions (17% of all exceptions in batch)
Deviation      negative mean -0.032% · CV 0.000 · direction consistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹0.03   (computed from these 3 records)
Projected monthly impact   ₹0.30  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Check the rounding mode used in the settlement system — expected half-up (Indian financial standard), but truncation appears to be applied on plan PLN_STD.

Narration (template): 3 exceptions share {'exception_code': 'E04', 'payment_method': 'netbanking', 'fee_plan_id': 'PLN_STD', 'card_network': None, 'is_international': False, 'is_refund': False, 'settlement_batch': 'STL_2026_08'}, covering 17% of exceptions in this batch — below the threshold to confirm a cause. Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Check the rounding mode used in the settlement system — expected half-up (Indian financial standard), but truncation appears to be applied on plan PLN_STD.

────────────────────────────────────────────────────────────────
RC_003   ○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE     confidence: LOW
────────────────────────────────────────────────────────────────
Shared         is_refund=True  ·  exception_code=E06  ·  payment_method=card  ·  card_network=visa  ·  fee_plan_id=PLN_STD  ·  is_international=False  ·  settlement_batch=STL_2026_08
Support        2 exceptions (11% of all exceptions in batch)
Deviation      negative mean 0.000% · CV 0.000 · direction inconsistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹0.00   (computed from these 2 records)
Projected monthly impact   ₹0.00  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Confirm whether the refund fee-reversal step is configured on plan PLN_STD — refund transactions are being settled without crediting back the original platform fee.

Narration (template): 2 exceptions share {'is_refund': True, 'exception_code': 'E06', 'payment_method': 'card', 'card_network': 'visa', 'fee_plan_id': 'PLN_STD', 'is_international': False, 'settlement_batch': 'STL_2026_08'}, covering 11% of exceptions in this batch — below the threshold to confirm a cause. Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Confirm whether the refund fee-reversal step is configured on plan PLN_STD — refund transactions are being settled without crediting back the original platform fee.

────────────────────────────────────────────────────────────────
RC_004   ○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE     confidence: LOW
────────────────────────────────────────────────────────────────
Shared         exception_code=E03  ·  payment_method=card  ·  is_refund=False  ·  card_network=visa  ·  fee_plan_id=PLN_STD  ·  is_international=False  ·  settlement_batch=STL_2026_08
Support        2 exceptions (11% of all exceptions in batch)
Deviation      positive mean 747.458% · CV 0.000 · direction consistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹352.80   (computed from these 2 records)
Projected monthly impact   ₹3,528.00  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Review the GST computation logic for card transactions on plan PLN_STD — tax appears to be computed on the gross transaction amount rather than on the platform fee.

Narration (template): 2 exceptions share {'exception_code': 'E03', 'payment_method': 'card', 'is_refund': False, 'card_network': 'visa', 'fee_plan_id': 'PLN_STD', 'is_international': False, 'settlement_batch': 'STL_2026_08'}, covering 11% of exceptions in this batch — below the threshold to confirm a cause. Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Review the GST computation logic for card transactions on plan PLN_STD — tax appears to be computed on the gross transaction amount rather than on the platform fee.

