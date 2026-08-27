# LEDGERSCOPE — END-TO-END DEMO RUN OUTPUT

## 1. Clean Terminal Execution & Raw Output

### Exact Command Used
```bash
cd /Users/pratheepselvam/Documents/razorpay_hackathon/ledgerscope
python3 -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm
```

### Full Raw Terminal Stdout
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

### Measured Wall-Clock Execution Time
* **Total Elapsed Time:** `0.140s` (140.0 ms)
* **CPU Consumption:** `0.07s user, 0.02s system (63% CPU)`

---

## 2. Extracted Run Metrics & Forensic Breakdown

### Aggregate Batch Metrics
* **Total Transactions Processed:** `62` paired records
* **Gross Ingested Volume:** `₹1,20,916.27` (12,091,627 paise)
* **Clean Match Count & Rate:** `44` transactions (`71.0%`)
* **Total Exceptions Count & Rate:** `18` transactions (`29.0%`)
* **Orphan Records:** `0` transaction orphans, `0` settlement orphans

### Exception Taxonomy Breakdown (E01–E09)
* **E01 (FEE_RATE_MISMATCH):** `10`
* **E02 (GST_RATE_MISMATCH):** `0`
* **E03 (GST_BASE_MISMATCH):** `2`
* **E04 (ROUNDING_DRIFT):** `3`
* **E05 (MISSING_TAX_LINE):** `1`
* **E06 (REFUND_FEE_NOT_REVERSED):** `2`
* **E07 (SETTLEMENT_TIMING):** `0`
* **E08 (DUPLICATE_DEDUCTION):** `0`
* **E09 (UNEXPLAINED):** `0`

---

### Root-Cause Findings Output

#### Finding 1: `RC_001`
* **Verdict & Confidence:** `● LIKELY ROOT CAUSE` — **HIGH CONFIDENCE**
* **Cause Type:** `RATE_MISCONFIGURATION`
* **Shared Attributes:** `fee_plan_id=PLN_ENT_2024 · exception_code=E01 · payment_method=netbanking`
* **Support Count:** `10` exceptions
* **Coverage Ratio:** `55.6%` (10 of 18 exceptions)
* **Observed Batch Financial Impact:** `₹33.32` (3,332 paise)
* **Projected Monthly Impact:** `₹333.20` (33,320 paise)
* **Exact Generated Remediation Sentence:**
  > *"Audit the netbanking rate on fee plan PLN_ENT_2024 — settlement is applying a rate inconsistent with the plan's configured rate."*

#### Finding 2: `RC_002`
* **Verdict & Confidence:** `○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE` — **MEDIUM CONFIDENCE**
* **Cause Type:** `ROUNDING_CONVENTION_MISMATCH`
* **Shared Attributes:** `fee_plan_id=PLN_STD · exception_code=E04 · payment_method=netbanking`
* **Support Count:** `3` exceptions
* **Coverage Ratio:** `16.7%` (3 of 18 exceptions)
* **Observed Batch Financial Impact:** `₹0.03` (3 paise)
* **Projected Monthly Impact:** `₹0.30` (30 paise)
* **Exact Generated Remediation Sentence:**
  > *"Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Check the rounding mode used in the settlement system — expected half-up (Indian financial standard), but truncation appears to be applied on plan PLN_STD."*

#### Finding 3: `RC_003`
* **Verdict & Confidence:** `○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE` — **LOW CONFIDENCE**
* **Cause Type:** `REFUND_FEE_NOT_REVERSED`
* **Shared Attributes:** `fee_plan_id=PLN_STD · exception_code=E06 · is_refund=True · payment_method=card · card_network=visa`
* **Support Count:** `2` exceptions
* **Coverage Ratio:** `11.1%` (2 of 18 exceptions)
* **Observed Batch Financial Impact:** `₹0.00` (0 paise)
* **Projected Monthly Impact:** `₹0.00` (0 paise)
* **Exact Generated Remediation Sentence:**
  > *"Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Confirm whether the refund fee-reversal step is configured on plan PLN_STD — refund transactions are being settled without crediting back the original platform fee."*

#### Finding 4: `RC_004`
* **Verdict & Confidence:** `○ POSSIBLE PATTERN — INSUFFICIENT EVIDENCE` — **LOW CONFIDENCE**
* **Cause Type:** `GST_BASE_ERROR`
* **Shared Attributes:** `fee_plan_id=PLN_STD · exception_code=E03 · payment_method=card · card_network=visa`
* **Support Count:** `2` exceptions
* **Coverage Ratio:** `11.1%` (2 of 18 exceptions)
* **Observed Batch Financial Impact:** `₹352.80` (35,280 paise)
* **Projected Monthly Impact:** `₹3,528.00` (352,800 paise)
* **Exact Generated Remediation Sentence:**
  > *"Monitor across the next 2-3 settlement batches before treating this as confirmed. If the pattern persists: Review the GST computation logic for card transactions on plan PLN_STD — tax appears to be computed on the gross transaction amount rather than on the platform fee."*

---

### Batch Delta & Monthly Projection Scaling
* **Observed Total Batch Delta:** `₹384.29` (38,429 paise)
* **Batch Duration Span:** `3 calendar days` (computed from transaction capture timestamps)
* **Monthly Scaling Factor:** `×10.0` (standard 30-day accounting month)
* **Projected Total Monthly Discrepancy Impact:** `₹3,842.90` (384,290 paise)

---

### Sample Flagged Exception Record (Full Raw Audit Record)

**Transaction ID: `TXN_0045` (E01 Rate Mismatch)**
```json
{
  "txn_id": "TXN_0045",
  "status": "EXCEPTION",
  "fee_plan": "PLN_ENT_2024",
  "payment_method": "netbanking",
  "gross_amount_paise": 999950,
  "gross_amount_inr": "₹9,999.50",
  "applied_rate_bps": 190,
  "implied_rate_bps": 200,
  "expected_fee_paise": 18999,
  "actual_fee_paise": 19999,
  "fee_delta_paise": 1000,
  "fee_delta_inr": "+₹10.00",
  "expected_tax_paise": 3420,
  "actual_tax_paise": 3600,
  "tax_delta_paise": 180,
  "tax_delta_inr": "+₹1.80",
  "total_delta_paise": 1180,
  "total_delta_inr": "+₹11.80",
  "deviation_ratio": 0.0526339,
  "exception_code": "E01",
  "rule_fired": "implied 200bps != applied 190bps"
}
```

---

## 3. Terminal vs. HTML Dashboard Cross-Verification

| Metric / Item | Terminal / Report Output | HTML Dashboard View | Status |
|---|---|---|---|
| **Total Transactions** | 62 records | 62 records | **EXACT MATCH** |
| **Matched Records** | 44 (71.0%) | 44 (71.0%) | **EXACT MATCH** |
| **Exception Records** | 18 (29.0%) | 18 (29.0%) | **EXACT MATCH** |
| **Net Batch Delta** | ₹384.29 | ₹384.29 | **EXACT MATCH** |
| **Projected Monthly Delta** | ₹3,842.90 | ₹3,842.90 | **EXACT MATCH** |
| **E01 Rate Exceptions** | 10 | 10 | **EXACT MATCH** |
| **E03 Tax Base Exceptions** | 2 | 2 | **EXACT MATCH** |
| **E04 Rounding Drift** | 3 | 3 | **EXACT MATCH** |
| **E05 Missing Tax Line** | 1 | 1 | **EXACT MATCH** |
| **E06 Refund Fee Unreversed** | 2 | 2 | **EXACT MATCH** |
| **Top Root Cause (RC_001)** | 10 txns (55.6% coverage) | 10 txns (55.6% coverage) | **EXACT MATCH** |
| **RC_001 Batch Impact** | ₹33.32 | ₹33.32 | **EXACT MATCH** |
| **RC_004 Batch Impact** | ₹352.80 | ₹352.80 | **EXACT MATCH** |

*Both the terminal engine and the client-side single-source-of-truth derived state in `dashboard.html` reflect the identical underlying data with zero delta discrepancies.*

---

## 4. Numbers to Say Out Loud in the Video

1. **62 paired transactions** ingested across a **3-day settlement batch**.
2. **71.0% clean match rate** (44 transactions verified with ₹0.00 variance).
3. **18 exceptions detected** (29.0% discrepancy rate across 5 distinct failure categories).
4. **₹384.29 net batch loss** scaling to **₹3,842.90 projected monthly recovery**.
5. **10 transactions on `PLN_ENT_2024`** overcharged at 2.00% instead of 1.90% (`RC_001`).
6. **55.6% coverage ratio** on the top root-cause finding, clearing the >50% promotion threshold.
7. **₹352.80 tax overcharge** detected on 2 card transactions where GST was erroneously levied on gross amounts (`RC_004`).
8. **140 milliseconds** total pipeline execution time for end-to-end ingestion, classification, and root-cause clustering.
