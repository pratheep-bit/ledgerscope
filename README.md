# Ledgerscope

> **Deterministic settlement fee reconciliation engine for Razorpay merchants.**

Ledgerscope ingests raw transaction and settlement CSVs, recomputes every expected fee and GST charge to the paise using **64-bit integer arithmetic**, classifies each discrepancy with a deterministic exception code, and runs pattern-based root-cause analysis across the full exception set — without a single floating-point monetary computation.

**Track: Razorpay Hackathon 2026 — Track 04: AI Finance Controller**

---

## The Problem

Settlement files tell you *that* something is wrong — not *why*. A finance controller looking at 18 exceptions across 62 transactions needs to know:

- Is this one misconfigured fee plan affecting 55% of exceptions?
- Or isolated noise from two unrelated transactions?

Ledgerscope answers that question deterministically, with mathematical proof and a one-line action for each finding.

---

## Real Output — Batch STL_2026_08 · 62 records · 3-day span

```
LEDGERSCOPE — batch STL_2026_08 · 62 records

  Matched       44 / 62      (71.0%)
  Exceptions    18 / 62      (29.0%)
  Unexplained    0 / 18      (E09 residual — zero)

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
Shared         fee_plan_id=PLN_ENT_2024 · exception_code=E01 · payment_method=netbanking
Support        10 exceptions (55.6% of all exceptions in batch)
Deviation      positive mean 5.268% · CV 0.006 · direction consistent

Observed batch impact      ₹33.32
Projected monthly impact   ₹333.20

→ ACTION  Audit the netbanking rate on fee plan PLN_ENT_2024 — the gateway
          is applying 2.00% against a configured rate of 1.90%.

────────────────────────────────────────────────────────────────
RC_004   ○ POSSIBLE PATTERN                   confidence: LOW
────────────────────────────────────────────────────────────────
Cause          GST_BASE_MISMATCH
Shared         fee_plan_id=PLN_STD · exception_code=E03 · payment_method=card
Support        2 exceptions
Deviation      GST charged on ₹1,000 gross (18% × ₹1,000 = ₹180.00) instead
               of ₹20 platform fee (18% × ₹20 = ₹3.60) — 50× overcharge

Observed batch impact      ₹352.80
Projected monthly impact   ₹3,528.00

Total batch discrepancy across all findings: ₹386.15
Projected monthly loss (30-day scale):       ₹3,861.50
```

Full machine-readable output: [`reports/report.json`](reports/report.json) · [`reports/report.md`](reports/report.md)

---

## Architecture

```
transactions.csv ─┐
settlements.csv   ├─► ingest.py ─► engine.py ─► classify.py ─► rootcause.py ─► narrate.py ─► report.py
fee_plans.json   ──┘
```

| Module | Role |
|--------|------|
| `rates.py` | Rate constants + half-up rounding; `float` never touches a monetary value |
| `models.py` | Frozen dataclasses: Transaction, Settlement, FeePlan, MatchResult |
| `ingest.py` | Load CSVs/JSON, inner-join on txn_id, surface orphans |
| `engine.py` | Recompute expected fee + GST per transaction (deterministic, integer paise) |
| `classify.py` | Exception cascade E01–E09, most-specific first, first-match wins |
| `rootcause.py` | Pattern detection across exceptions; deduplicated candidate collapsing |
| `narrate.py` | Plain-English narration; falls back to deterministic template if LLM invents a number |
| `report.py` | Write `report.json`, `report.md`, `audit.jsonl` |
| `generate.py` | 62-record synthetic batch (seeded, reproducible) |
| `run.py` | CLI entrypoint |

---

## Key Design Decisions

**Integer paise throughout.**
`float` is banned for monetary values. Every fee, tax, and delta is stored and computed as `int` paise. `deviation_ratio` is the only float — it is diagnostic only and is never summed into a rupee amount.

**Statutory half-up rounding.**
Python's `round()` uses banker's rounding. Indian financial convention requires half-up. On a GST line landing on exactly 0.5 paise — which occurs at predictable cadences — the two conventions diverge by 1 paise. Getting this wrong would make the engine manufacture the E04 signal it claims to find.

**Coverage-gated root cause promotion.**
```
likely_root_cause  ⟺  support ≥ 2  AND  coverage > 0.50  AND  sign_consistent
anything else      →  "possible_pattern — insufficient evidence"
```
A 2-row outlier with a 50× rupee impact cannot displace a 10-row systemic misconfiguration affecting 55% of exceptions. Coverage promotes — not money.

**Numeric token hallucination guard.**
`narrate.py` checks every numeric token in LLM output against the set of numbers already computed in the finding dict. If the model synthesises any figure not present in the computed result, narration falls back to a deterministic template. The guard is tested end-to-end in `test_narrate_falls_back_on_hallucination`.

**Deduplicated findings.**
Candidates with identical member sets (`frozenset(affected_txn_ids)`) are collapsed into a single finding. Attributes with zero discriminating variance across the exception set are pruned before promotion.

---

## Exception Taxonomy

| Code | Name | Trigger |
|------|------|---------|
| E01 | `FEE_RATE_MISMATCH` | implied_rate_bps ≠ applied_rate_bps by > 1 bp |
| E02 | `GST_RATE_MISMATCH` | fee correct; tax/fee implies GST ≠ 18% by > 10 bps |
| E03 | `GST_BASE_MISMATCH` | tax computed on gross_paise instead of fee_paise |
| E04 | `ROUNDING_DRIFT` | \|total_delta\| ≤ 2 paise and rates otherwise correct |
| E05 | `MISSING_TAX_LINE` | tax_paise is None/0 while fee_paise > 0 |
| E06 | `REFUND_FEE_NOT_REVERSED` | is_refund and fee not credited back |
| E07 | `SETTLEMENT_TIMING` | settled outside expected settlement cycle window |
| E08 | `DUPLICATE_DEDUCTION` | two settlement rows for one txn_id |
| E09 | `UNEXPLAINED` | none of the above — always reported, never suppressed |

> E02, E07, E08 are in the taxonomy but unexercised in the 62-record batch. Documented in [`FAILURES.md`](FAILURES.md) rather than hidden.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate synthetic test batch (seeded, reproducible)
python -m ledgerscope.generate --seed 42

# Run reconciliation (no LLM required)
python -m ledgerscope.run --batch synthetic/ --out reports/ --no-llm

# Run full test suite
pytest -v
```

---

## Validation & Benchmarks

All metrics are measured end-to-end on live runs. No cherry-picking.

### Statistical Accuracy — 200 Independent Synthetic Batches

```bash
python test_statistical_validation.py
```

| Test | Batches | Result | Target | Verdict |
|------|:-------:|:------:|:------:|:-------:|
| **False Positive Rate** (pure noise batches) | 100 | **0.0%** (0 / 100) | 0.0% | ✅ PASS |
| **Recall Rate** (injected systemic defects) | 100 | **100.0%** (100 / 100) | ≥ 95.0% | ✅ PASS |

Full results: [`results_statistical_validation.md`](results_statistical_validation.md)

### Throughput Benchmark — 5,000 Paired Records, 3 Runs

```bash
python test_throughput_benchmark.py
```

| Metric | Run 1 | Run 2 | Run 3 | Median |
|--------|------:|------:|------:|-------:|
| Wall-clock | 256.98 ms | **234.39 ms** | 229.84 ms | **234.39 ms** |
| Throughput | 19,456.5 rec/s | **21,332.1 rec/s** | 21,754.2 rec/s | **21,332.1 rec/s** |
| Peak RAM | 3.60 MB | 3.29 MB | 3.29 MB | **3.29 MB** |

**21,332 paired records/second** on a single CPU core. No GPU, no cloud API, no LLM inference cost.

Full results: [`results_throughput_benchmark.md`](results_throughput_benchmark.md)

---

## Test Suite

```bash
pytest -v   # 39 tests, all green, under 2.1 seconds
```

| Test File | What It Proves |
|-----------|---------------|
| `tests/test_engine.py` | Fee + GST recomputation; anchor transaction ₹1,337.49 @ 200bps = 2675p fee, 482p GST (half-up from 481.5) |
| `tests/test_rates.py` | Statutory half-up rounding at every `.5` boundary |
| `tests/test_classify.py` | Deterministic exception cascade E01–E09 |
| `tests/test_rootcause.py` | Cluster promotion, weak-pattern rejection, outlier isolation, deduplication |
| `tests/test_narrate.py` | Hallucination guard fires and falls back to template |
| `tests/test_ingest.py` | CSV loading, strict boolean parsing, orphan tracking |
| `tests/test_statistical_validation.py` | 0.0% FPR, 100.0% recall across 200 batches |
| `tests/test_throughput_benchmark.py` | Throughput ≥ 500 rec/s threshold |

---

## Honest Limitations

See [`FAILURES.md`](FAILURES.md) for a complete, unedited list of known limitations, including:

- **RC_003 arithmetic delta is ₹0.00** — the engine correctly classifies the semantic violation (E06: refund fee not reversed) but the arithmetic delta against the standard baseline is zero paise. The classification is correct; the financial impact quantification needs a refund-specific baseline in v1.1.
- **E02, E07, E08** are in the taxonomy but not exercised in the current 62-record synthetic batch.
- **Monthly projections** are a simple × (30 / batch_days) scale — no seasonality or volume modelling.

---

## Rate Basis

| Parameter | Value | Source |
|-----------|-------|--------|
| Standard MDR | 2% + 18% GST on fee | razorpay.com/pricing |
| RuPay Credit on UPI | 2.15% + 18% GST | razorpay.com/pricing |
| International cards | 3% + 18% GST | Modelled assumption |
| Zero-MDR instruments | Standard UPI, RuPay Debit | NPCI policy |
| Negotiated plans | Sub-2% enterprise rates | `synthetic/fee_plans.json` |
| Fetched | 2026-08-22 | — |

---

## Audit Trail

Every reconciliation run produces:

- **`report.json`** — machine-readable full finding set
- **`report.md`** — human-readable narrative with action items
- **`audit.jsonl`** — per-transaction computation log for dispute filing

[`AUDIT.md`](AUDIT.md) contains the full independent audit with raw command outputs verifying every claimed metric.
