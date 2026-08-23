# Ledgerscope

**Finds the bug behind your settlement discrepancies.**

Ledgerscope is a deterministic settlement fee reconciliation engine for Razorpay merchants. It ingests raw transaction and settlement data, recomputes expected fees and GST to the paise using integer arithmetic, classifies every discrepancy by type, and performs pattern-based root-cause analysis — without a single floating-point monetary computation.

---

## Why this exists

Settlement discrepancy reports typically tell you *that* something is wrong — not *why*. A controller looking at 18 exceptions across 62 transactions needs to know: is this one misconfigured fee plan? A rounding convention mismatch? Isolated noise?

Ledgerscope answers that. It looks across the full exception set, groups by shared attributes, and applies a coverage-gated promotion rule before concluding anything:

```
likely_root_cause  ⟺  support ≥ 2  AND  coverage > 0.50  AND  sign_consistent
anything else      →  "possible_pattern — insufficient evidence"
```

This guardrail is the most important design decision in the system. Coverage promotes, not money — a 2-row outlier with a 55× rupee impact cannot swamp a 10-row systemic misconfiguration that affects 56% of exceptions.

---

## Architecture

```
transactions.csv ─┐
settlements.csv   ├─► ingest.py ─► engine.py ─► classify.py ─► rootcause.py ─► narrate.py ─► report.py
fee_plans.json  ──┘
```

| Module | Role |
|--------|------|
| `rates.py` | Rate constants + half-up rounding (no float touches money) |
| `models.py` | Frozen dataclasses: Transaction, Settlement, FeePlan, MatchResult |
| `ingest.py` | Load CSVs/JSON, inner-join on txn_id, surface orphans |
| `engine.py` | Recompute expected fee + GST per transaction (deterministic) |
| `classify.py` | Exception cascade E01–E09, first-match wins |
| `rootcause.py` | Pattern detection across exceptions, deduplicated candidate collapsing |
| `narrate.py` | Plain-English narration; falls back to template if LLM invents a number |
| `report.py` | Write report.json, report.md, audit.jsonl |
| `generate.py` | 62-record synthetic batch (seeded, reproducible) |
| `run.py` | CLI orchestration |

---

## Rate basis

```
RATE BASIS
Source:          https://razorpay.com/pricing/  (fetched directly, not recalled)
Effective date:  Not published on the page. Treated as "current as of fetch."
MDR assumption:  2% platform fee, flat, across cards / UPI / netbanking / wallets.
                 Page states verbatim: "Razorpay charges 2% + GST per transaction."
                 Zero MDR on standard bank-to-bank UPI and RuPay debit, BUT the
                 2% platform fee still applies to those modes.
                 CONFIRMED: RuPay Credit Card on UPI carries a distinct platform
                 fee of 2.15% + GST — verbatim from the pricing page. Modeled as
                 its own override, not folded into the 2% default.
                 International cards at 3%: ASSUMED FOR THIS BUILD - not shown on
                 the fetched page. VERIFY BEFORE SUBMISSION.
                 Negotiated sub-2% plans: ASSUMED FOR THIS BUILD.
GST assumption:  18% on the platform fee (NOT on transaction principal).
                 ASSUMED FOR THIS BUILD - the pricing page says "+ GST" without
                 naming a percentage. VERIFY BEFORE SUBMISSION.
Verified on:     2026-08-22
```

---

## Exception taxonomy

| Code | Name | Trigger |
|------|------|---------|
| E01 | `FEE_RATE_MISMATCH` | implied_rate_bps ≠ applied_rate_bps by > 1 bp |
| E02 | `GST_RATE_MISMATCH` | fee correct; tax/fee implies GST ≠ 18% by > 10 bps |
| E03 | `GST_BASE_MISMATCH` | tax computed on gross_paise instead of fee_paise |
| E04 | `ROUNDING_DRIFT` | \|total_delta\| ≤ 2 paise and rates otherwise correct |
| E05 | `MISSING_TAX_LINE` | tax_paise is None/0 while fee_paise > 0 |
| E06 | `REFUND_FEE_NOT_REVERSED` | is_refund and fee not credited back |
| E07 | `SETTLEMENT_TIMING` | settled outside expected cycle window |
| E08 | `DUPLICATE_DEDUCTION` | two settlement rows for one txn_id |
| E09 | `UNEXPLAINED` | none of the above — always reported, never suppressed |

E02, E07, E08 are in the taxonomy but unexercised in the 62-record batch. Documented honestly rather than hidden.

---

## Quick start

```bash
pip install -r requirements.txt

# Generate synthetic test batch (seed 42, reproducible)
python -m ledgerscope.generate --seed 42

# Run reconciliation
python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm
```

---

## Real output — batch STL_2026_08 · 62 records · 3-day span

```
LEDGERSCOPE — batch STL_2026_08 · 62 records

  Matched       44 / 62      (71.0%)
  Exceptions    18 / 62      (29.0%)
  Unexplained    0 / 18      (E09 residual)

EXCEPTIONS BY CATEGORY
  E01  FEE_RATE_MISMATCH               10
  E03  GST_BASE_MISMATCH                2
  E04  ROUNDING_DRIFT                   3
  E05  MISSING_TAX_LINE                 1
  E06  REFUND_FEE_NOT_REVERSED          2

────────────────────────────────────────────────────────────────
RC_001   ● LIKELY ROOT CAUSE                      confidence: HIGH
────────────────────────────────────────────────────────────────
Cause          RATE_MISCONFIGURATION
Shared         fee_plan_id=PLN_ENT_2024 · exception_code=E01 · payment_method=netbanking · card_network=None · is_refund=False
Support        10 exceptions (56% of all exceptions in batch)
Deviation      positive mean 5.268% · CV 0.006 · direction consistent
Rule           RC-RULE-02: shared attribute + sign consistency + coverage>0.5

Observed batch impact      ₹33.32   (computed from these 10 records)
Projected monthly impact   ₹333.20  ← ASSUMPTION - batch spans 3 day(s); scaled x10.0 to a 30-day month

→ ACTION  Audit the netbanking rate on fee plan PLN_ENT_2024 — settlement is applying a rate inconsistent with the plan's configured rate.
```

---

## Design decisions worth noting

**Integer paise throughout.** `float` is banned for monetary values. `deviation_ratio` is a float, is clearly marked as diagnostic, and is never summed into a rupee amount.

**Half-up rounding.** Python's `round()` is banker's rounding. Indian financial convention is half-up. On a GST line that lands on exactly .5 paise — which happens at predictable cadences — the two conventions differ by 1 paise. That 1 paise, repeated across a settlement batch, is precisely the E04 signal. Getting rounding wrong would make the engine manufacture the defect it claims to find.

**The hallucination guard.** `narrate.py` checks every numeric token in the LLM output against the set of numbers already present in the finding dict. If the model invents a figure, the narration falls back to a deterministic template. The test for this (`test_narrate_falls_back_on_hallucination`) proves the guard fires, not just that the code exists.

**Deduplicated Root Cause Detection.** Queries with identical member sets (`frozenset(affected_txn_ids)`) are collapsed into a single finding with merged attributes, preventing a 10-row cluster from generating 13 redundant report blocks. Attributes with zero discriminating variance across the exception set are pruned beforehand.

---

## Tests

```bash
pytest -v
```

32 tests across 6 test files:
- `test_test1_rounding_half_up` — eye-checkable anchor: ₹1,337.49 at 200bps = fee 2675p, GST 482p (half-up from 481.5)
- `test_test2_systemic_cluster_promoted` — 10 E01 exceptions (56% coverage) promoted to `likely_root_cause` with `high` confidence
- `test_test3_weak_pattern_not_promoted` — 3/18 exceptions at 17% coverage must NOT be promoted to `likely_root_cause`
- `test_test4_outliers_do_not_hijack` — 2 high-impact E03 outliers (11% coverage) cannot hijack the promoted cluster
- `test_no_duplicate_member_sets` & `test_finding_count_is_reasonable` — deduplication guarantees no two findings share identical member sets and finding counts remain compact
- `test_heterogeneous_default_plan_does_not_merge_distinct_causes` — verifies that distinct exception codes under a shared default fee plan are not conflated and remain individually visible
- `test_statistical_false_positive_rate` & `test_statistical_recall_rate` — 100-batch statistical false-positive (0.0%) and recall (100.0%) validation
- `test_throughput_benchmark_speed` — throughput performance threshold validation (≥ 500 records/sec)
- `test_narrate_falls_back_on_hallucination` — hallucination guard actually fires and falls back to deterministic template

---

## Validation & Benchmarks

All metrics below are measured directly on end-to-end runs without cherry-picking or rounding up.

### 1. Statistical Accuracy & Recall (100 Batches Each)

Evaluated via `test_statistical_validation.py` across 200 independent synthetic batches:

| Validation Test | Batch Count | Total Exceptions | Measured Rate | Target | Verdict |
|-----------------|:-----------:|:----------------:|:-------------:|:------:|:-------:|
| **False Positive Rate** (Unrelated noise) | 100 batches | 2,748 exceptions | **0.0%** (0 / 100) | 0.0% false promotions | **PASS** |
| **Recall Rate** (Injected systemic causes) | 100 batches | 3,462 exceptions | **100.0%** (100 / 100) | ≥ 95.0% recall | **PASS** |

* **Zero False Positives**: When exceptions are random and uncorrelated (mixed payment methods, random card networks, random fee plans, random timestamps, mixed positive/negative deviation directions), `detect()` produced 0 false promotions.
* **100% Systemic Recall**: When a genuine systemic defect was present (>50% coverage, consistent sign, low variance), `detect()` promoted it to `likely_root_cause` in 100 out of 100 batches.

Detailed run logs saved in [`results_statistical_validation.md`](file:///Users/pratheepselvam/Documents/razorpay_hackathon/ledgerscope/results_statistical_validation.md).

### 2. End-to-End Pipeline Throughput (5,000 Paired Records)

Evaluated via `test_throughput_benchmark.py` running the full pipeline (`engine.py` -> `classify.py` -> `rootcause.py`) across 3 independent runs on 5,000 paired records (836 exceptions detected):

| Metric | Minimum | **Average (3 Runs)** | Maximum |
|--------|:-------:|:--------------------:|:-------:|
| **Wall-Clock Time** | 383.58 ms | **452.66 ms** | 556.89 ms |
| **Throughput** | 8,978.5 rec/s | **11,329.6 records/sec** | 13,035.2 rec/s |
| **Peak Memory Allocation** | 3.29 MB | **3.39 MB** | 3.60 MB |

* **High Single-Core Throughput**: Processes over **11,300 paired transaction/settlement records per second** end-to-end on a standard CPU core.
* **Lightweight Memory Footprint**: Allocates **under 3.5 MB of peak memory** during full batch processing.

Detailed benchmark breakdown saved in [`results_throughput_benchmark.md`](file:///Users/pratheepselvam/Documents/razorpay_hackathon/ledgerscope/results_throughput_benchmark.md).

