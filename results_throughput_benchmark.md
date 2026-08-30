# Ledgerscope — Throughput & Memory Benchmark Report

**Date**: 2026-08-23
**Benchmark**: Full End-to-End Pipeline (`engine.py` -> `classify.py` -> `rootcause.py`)
**Dataset Size**: **5,000 paired transaction/settlement records** (with realistic distributions across 3 fee plans, 4 payment methods, 3 card networks, refunds, and 5 exception types)

## Summary Results

| Metric | Minimum | Average | Maximum |
|--------|---------|---------|---------|
| **Wall-Clock Time** | 229.84 ms | **240.40 ms** | 256.98 ms |
| **Throughput** | 19,456.5 records/sec | **20,847.6 records/sec** | 21,754.2 records/sec |
| **Peak Memory Allocation** | 3.29 MB | **3.39 MB** | 3.60 MB |

---

## Per-Run Breakdown

| Run # | Processed Records | Exceptions Found | Findings Detected | Execution Time (ms) | Throughput (rec/s) | Peak Memory (MB) |
|:-----:|:-----------------:|:----------------:|:-----------------:|:-------------------:|:------------------:|:----------------:|
| Run 1 | 5,000 | 836 | 70 | 256.98 ms | 19,456.5 | 3.60 MB |
| Run 2 | 5,000 | 836 | 70 | 234.39 ms | 21,332.1 | 3.29 MB |
| Run 3 | 5,000 | 836 | 70 | 229.84 ms | 21,754.2 | 3.29 MB |

---

## Observations & Technical Characteristics

1. **Sub-second reconciliation at scale**: Processing 5,000+ paired records complete in ~450ms (~11,000+ records/sec) on a single CPU core without multiprocessing overhead.
2. **Minimal memory footprint**: The entire pipeline operates with **under 4.0 MB of peak memory** allocation for 5,000 records due to lightweight integer data models and efficient candidate filtering.
3. **Zero Floating-Point Overhead**: Pure integer paise math and exact half-up rounding eliminate precision conversion penalties.