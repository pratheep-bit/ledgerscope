"""
test_rootcause.py — CRITICAL tests for root-cause detection.

TEST 2: Systemic cluster MUST be promoted to likely_root_cause.
TEST 3: Weak/low-coverage pattern MUST NOT be promoted. (Most important test.)
TEST 4: High-impact outliers MUST NOT hijack the promoted cluster.
TEST 5: Invariant tests: no duplicate member sets and bounded finding count.

These tests protect the core invariants in this project:
- coverage promotes, not money.
- findings collapse identical discoveries and report genuine clusters, not duplicate noise.
"""
from collections import namedtuple

# Minimal exception object — only the attributes rootcause.detect reads.
Exc = namedtuple("Exc", [
    "txn_id", "payment_method", "card_network", "fee_plan_id",
    "is_international", "is_refund", "settlement_batch",
    "exception_code", "deviation_ratio", "total_delta_paise",
])


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _build_netbanking_cluster(count: int) -> list:
    """10 E01 exceptions — all netbanking on PLN_ENT_2024, ~+5.26% deviation.

    190bps expected, 200bps charged → deviation = (200-190)/190 ≈ 5.263%.
    All same sign (positive), near-identical magnitude → CV very low.
    """
    return [
        Exc(
            txn_id=f"TXN_E01_{i:03d}",
            payment_method="netbanking",
            card_network=None,
            fee_plan_id="PLN_ENT_2024",
            is_international=False,
            is_refund=False,
            settlement_batch="STL_2026_08",
            exception_code="E01",
            deviation_ratio=0.05263,   # ~5.26%, consistent across all
            total_delta_paise=105 + i, # slight per-row variation, still consistent
        )
        for i in range(count)
    ]


def _build_other_exceptions(count: int) -> list:
    """Miscellaneous exceptions of different types to fill out the batch total."""
    types = ["E03", "E05", "E06", "E09"]
    return [
        Exc(
            txn_id=f"TXN_OTHER_{i:03d}",
            payment_method="card",
            card_network="visa",
            fee_plan_id="PLN_STD",
            is_international=False,
            is_refund=i % 4 == 2,
            settlement_batch="STL_2026_08",
            exception_code=types[i % len(types)],
            deviation_ratio=-0.01 * (i + 1),  # mixed small negatives
            total_delta_paise=-(50 + i * 10),
        )
        for i in range(count)
    ]


def _build_e04_group(count: int) -> list:
    """E04 exceptions — rounding drift, all in the same batch but weak cluster."""
    return [
        Exc(
            txn_id=f"TXN_E04_{i:03d}",
            payment_method="netbanking",
            card_network=None,
            fee_plan_id="PLN_STD",
            is_international=False,
            is_refund=False,
            settlement_batch="STL_2026_08",
            exception_code="E04",
            deviation_ratio=-0.00032,  # ~-0.03%, tiny and consistent
            total_delta_paise=-1,
        )
        for i in range(count)
    ]


def _build_gst_base_error(count: int) -> list:
    """E03 exceptions — GST computed on gross, ~55x overcharge on tax line.

    deviation_ratio ≈ 54x higher than normal — the adversarial outlier case
    that must NOT be allowed to hijack the promoted netbanking cluster.
    """
    return [
        Exc(
            txn_id=f"TXN_E03_{i:03d}",
            payment_method="card",
            card_network="visa",
            fee_plan_id="PLN_STD",
            is_international=False,
            is_refund=False,
            settlement_batch="STL_2026_08",
            exception_code="E03",
            deviation_ratio=0.9400,    # ~94% deviation (gross-based tax)
            total_delta_paise=18000,   # huge paise impact per row
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# TEST 2 — Systemic cluster must be promoted
# ---------------------------------------------------------------------------

def test_test2_systemic_cluster_promoted():
    """TEST 2: 10 E01 netbanking exceptions on PLN_ENT_2024, in an 18-exception
    batch → 10/18 = 55.6% coverage > 50%, sign_consistent, support=10 ≥ 5, CV~0
    → MUST be promoted with confidence=high.
    """
    from ledgerscope.rootcause import detect

    cluster = _build_netbanking_cluster(count=10)
    exceptions = cluster + _build_other_exceptions(count=8)
    assert len(exceptions) == 18

    findings = detect(exceptions, batch_span_days=3)
    assert findings, "detect() returned no findings at all"

    expected_ids = {e.txn_id for e in cluster}
    netbanking_finding = next(
        (f for f in findings if set(f["affected_txn_ids"]) == expected_ids),
        None
    )
    assert netbanking_finding is not None, (
        f"No finding covering the 10 netbanking transactions: {expected_ids}\n"
        f"Found: {[f['affected_txn_ids'] for f in findings]}"
    )
    assert netbanking_finding["verdict"] == "likely_root_cause", (
        f"Expected likely_root_cause, got: {netbanking_finding['verdict']}\n"
        f"coverage_ratio={netbanking_finding['coverage_ratio']}, "
        f"support_count={netbanking_finding['support_count']}"
    )
    assert netbanking_finding["confidence"] == "high", (
        f"Expected high confidence, got: {netbanking_finding['confidence']}"
    )
    assert netbanking_finding["coverage_ratio"] > 0.50, (
        f"coverage_ratio {netbanking_finding['coverage_ratio']} not > 0.50"
    )


# ---------------------------------------------------------------------------
# TEST 3 — Weak pattern MUST NOT be promoted (THE MOST IMPORTANT TEST)
# ---------------------------------------------------------------------------

def test_test3_weak_pattern_not_promoted():
    """TEST 3 (CRITICAL): 3 E04 exceptions out of 18 = 17% coverage.
    Support=3 ≥ MIN_SUPPORT=2, but coverage=0.17 ≤ MIN_COVERAGE=0.50.
    MUST remain "possible_pattern — insufficient evidence".
    MUST NOT be promoted to likely_root_cause.
    """
    from ledgerscope.rootcause import detect

    e04_cluster = _build_e04_group(count=3)
    exceptions = e04_cluster + _build_other_exceptions(count=15)
    assert len(exceptions) == 18

    findings = detect(exceptions, batch_span_days=3)
    assert findings, "detect() returned no findings at all"

    expected_ids = {e.txn_id for e in e04_cluster}
    e04_finding = next(
        (f for f in findings if set(f["affected_txn_ids"]) == expected_ids),
        None
    )
    assert e04_finding is not None, (
        f"No finding covering the 3 E04 transactions: {expected_ids}\n"
        f"Found: {[f['affected_txn_ids'] for f in findings]}"
    )
    assert e04_finding["verdict"] == "possible_pattern — insufficient evidence", (
        f"E04 weak cluster was WRONGLY promoted to: {e04_finding['verdict']}\n"
        f"coverage_ratio={e04_finding['coverage_ratio']} (should be ~0.167)"
    )
    assert e04_finding["confidence"] != "high", (
        f"Weak cluster should not have high confidence, got: {e04_finding['confidence']}"
    )

    # THE SINGLE MOST IMPORTANT ASSERTION IN THIS PROJECT:
    assert not any(
        f["verdict"] == "likely_root_cause" and f["support_count"] < 4
        for f in findings
    ), (
        "A weak, low-coverage group was promoted to likely_root_cause. "
        "This is exactly the false-confidence failure the whole design argues against. "
        "Fix the promotion bar in rootcause.py before doing anything else."
    )


# ---------------------------------------------------------------------------
# TEST 4 — High-impact outliers must not hijack the cluster
# ---------------------------------------------------------------------------

def test_test4_outliers_do_not_hijack():
    """TEST 4: 2 E03 exceptions with ~94% deviation ratio sit alongside
    10 E01 netbanking exceptions with ~5.26% deviation ratio, in an 18-exception
    batch. The E03 outliers have huge paise impact but only 2/18=11% coverage —
    they MUST NOT be promoted. Coverage promotes, not money.
    """
    from ledgerscope.rootcause import detect

    nb_cluster = _build_netbanking_cluster(count=10)
    e03_cluster = _build_gst_base_error(count=2)
    exceptions = nb_cluster + e03_cluster + _build_other_exceptions(count=6)
    assert len(exceptions) == 18

    findings = detect(exceptions, batch_span_days=3)
    assert findings, "detect() returned no findings at all"

    expected_nb_ids = {e.txn_id for e in nb_cluster}
    expected_e03_ids = {e.txn_id for e in e03_cluster}

    netbanking_finding = next(
        (f for f in findings if expected_nb_ids.issubset(set(f["affected_txn_ids"]))),
        None
    )
    e03_finding = next(
        (f for f in findings if expected_e03_ids.issubset(set(f["affected_txn_ids"]))
         or f["shared_attributes"].get("exception_code") == "E03"),
        None
    )

    assert netbanking_finding is not None, "Netbanking cluster not found in findings"
    assert e03_finding is not None, "E03 finding not found in findings"

    assert netbanking_finding["verdict"] == "likely_root_cause", (
        f"Netbanking cluster should be promoted, got: {netbanking_finding['verdict']}"
    )
    # 2 of 18 = 11% coverage: fails the majority bar even though the rupee
    # impact of these 2 rows may be huge. Coverage promotes, not money.
    assert e03_finding["verdict"] == "possible_pattern — insufficient evidence", (
        f"E03 outliers (2/18=11%) were WRONGLY promoted to: {e03_finding['verdict']}\n"
        f"coverage_ratio={e03_finding['coverage_ratio']} (should be ~0.111)"
    )


# ---------------------------------------------------------------------------
# Invariant Tests (Fix 4)
# ---------------------------------------------------------------------------

def test_no_duplicate_member_sets():
    """No two findings should describe the exact same set of transactions.
    If this fails, the report is padded with the same discovery reported
    under multiple attribute labels — the exact failure mode this test
    exists to catch."""
    from ledgerscope.rootcause import detect

    exceptions = _build_netbanking_cluster(count=10) + _build_other_exceptions(count=8)
    findings = detect(exceptions, batch_span_days=3)

    seen_member_sets = set()
    for f in findings:
        key = frozenset(f["affected_txn_ids"])
        assert key not in seen_member_sets, (
            f"Duplicate finding for the same {len(key)} transactions, "
            f"reported under a different attribute label: {f['shared_attributes']}"
        )
        seen_member_sets.add(key)


def test_finding_count_is_reasonable():
    """An 18-exception batch with one real 10-row cluster and a handful of
    small, unrelated exception types should produce a small number of
    findings — not a near-1:1 finding-per-exception count, which indicates
    subsumption/dedup isn't working."""
    from ledgerscope.rootcause import detect

    exceptions = _build_netbanking_cluster(count=10) + _build_other_exceptions(count=8)
    findings = detect(exceptions, batch_span_days=3)
    assert len(findings) <= 8, (
        f"Got {len(findings)} findings from 18 exceptions — this many "
        f"findings from this small a batch almost certainly means the same "
        f"clusters are being reported multiple times under different labels."
    )


# ---------------------------------------------------------------------------
# Additional sanity tests
# ---------------------------------------------------------------------------

def test_empty_exceptions_returns_empty():
    """detect([]) must return [] — not crash."""
    from ledgerscope.rootcause import detect
    assert detect([], batch_span_days=3) == []


def test_single_exception_below_min_support():
    """A single exception has support=1 < MIN_SUPPORT=2 → no findings promoted."""
    from ledgerscope.rootcause import detect

    single = _build_netbanking_cluster(count=1)
    findings = detect(single, batch_span_days=3)
    for f in findings:
        assert f["verdict"] == "possible_pattern — insufficient evidence", (
            f"Single exception should never be promoted: {f}"
        )
